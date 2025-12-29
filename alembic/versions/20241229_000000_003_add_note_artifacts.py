"""Add note artifacts tables for multimodal content extraction.

Revision ID: 003
Revises: 002
Create Date: 2024-12-29

Tables:
- note_artifacts: Base table for all extracted artifacts
- table_artifacts: Structured table data
- image_artifacts: Image metadata and analysis
- code_artifacts: Code block analysis
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create note_artifacts table
    op.create_table(
        'note_artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            'note_id',
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey('notes.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('artifact_type', sa.String(20), nullable=False),
        sa.Column('position_in_source', sa.Integer, nullable=False),
        sa.Column('context_before', sa.Text, nullable=True),
        sa.Column('context_after', sa.Text, nullable=True),
        sa.Column('raw_content', sa.Text, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('combined_text_for_embedding', sa.Text, nullable=True),
        sa.Column('qdrant_point_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('processing_status', sa.String(20), default='pending'),
        sa.Column('processing_error', sa.Text, nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Indexes for note_artifacts
    op.create_index('ix_note_artifacts_note_id', 'note_artifacts', ['note_id'])
    op.create_index('ix_note_artifacts_user_id', 'note_artifacts', ['user_id'])
    op.create_index('ix_note_artifacts_artifact_type', 'note_artifacts', ['artifact_type'])
    op.create_index('ix_note_artifacts_note_type', 'note_artifacts', ['note_id', 'artifact_type'])
    op.create_index('ix_note_artifacts_user_type', 'note_artifacts', ['user_id', 'artifact_type'])
    
    # Create table_artifacts table
    op.create_table(
        'table_artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            'artifact_id',
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey('note_artifacts.id', ondelete='CASCADE'),
            nullable=False,
            unique=True,
        ),
        sa.Column('raw_markdown', sa.Text, nullable=False),
        sa.Column('structured_json', postgresql.JSONB, nullable=True),
        sa.Column('row_facts', postgresql.JSONB, default=[]),
        sa.Column('row_fact_qdrant_ids', postgresql.JSONB, default=[]),
        sa.Column('row_count', sa.Integer, nullable=True),
        sa.Column('column_count', sa.Integer, nullable=True),
    )
    
    # Create image_artifacts table
    op.create_table(
        'image_artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            'artifact_id',
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey('note_artifacts.id', ondelete='CASCADE'),
            nullable=False,
            unique=True,
        ),
        sa.Column('s3_key', sa.String(500), nullable=True),
        sa.Column('s3_url', sa.String(1000), nullable=True),
        sa.Column('original_url', sa.String(2000), nullable=True),
        sa.Column('image_type', sa.String(50), nullable=True),
        sa.Column('components', postgresql.JSONB, default=[]),
        sa.Column('relationships', postgresql.JSONB, default=[]),
        sa.Column('ocr_text', sa.Text, nullable=True),
        sa.Column('data_points', postgresql.JSONB, nullable=True),
        sa.Column('width', sa.Integer, nullable=True),
        sa.Column('height', sa.Integer, nullable=True),
        sa.Column('format', sa.String(20), nullable=True),
        sa.Column('size_bytes', sa.Integer, nullable=True),
    )
    
    # Create code_artifacts table
    op.create_table(
        'code_artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            'artifact_id',
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey('note_artifacts.id', ondelete='CASCADE'),
            nullable=False,
            unique=True,
        ),
        sa.Column('language', sa.String(50), nullable=True),
        sa.Column('raw_code', sa.Text, nullable=False),
        sa.Column('explanation', sa.Text, nullable=True),
        sa.Column('extracted_concepts', postgresql.JSONB, default=[]),
        sa.Column('is_mermaid', sa.Integer, default=0),
        sa.Column('mermaid_type', sa.String(50), nullable=True),
        sa.Column('mermaid_components', postgresql.JSONB, default=[]),
        sa.Column('mermaid_relationships', postgresql.JSONB, default=[]),
    )
    
    # Add extraction columns to notes table
    op.add_column(
        'notes',
        sa.Column(
            'knowledge_extracted_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='When knowledge was last extracted from this note'
        )
    )
    op.add_column(
        'notes',
        sa.Column(
            'artifact_count',
            sa.Integer,
            default=0,
            nullable=True,
            comment='Number of artifacts extracted from this note'
        )
    )


def downgrade() -> None:
    # Drop columns from notes
    op.drop_column('notes', 'artifact_count')
    op.drop_column('notes', 'knowledge_extracted_at')
    
    # Drop artifact tables
    op.drop_table('code_artifacts')
    op.drop_table('image_artifacts')
    op.drop_table('table_artifacts')
    op.drop_table('note_artifacts')
