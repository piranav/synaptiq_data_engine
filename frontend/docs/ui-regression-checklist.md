# UI Regression Checklist

Use this checklist during redesign and future styling changes to verify all features still work.

## Global
- [ ] Theme switch works (`light`, `dark`, `system`) and persists after reload.
- [ ] Desktop/tablet/mobile layouts render without clipped content.
- [ ] Mobile bottom dock navigation works on dashboard routes.
- [ ] Keyboard focus is visible on interactive controls.
- [ ] `prefers-reduced-motion` does not break interactions.

## Home (`/home`)
- [ ] Dashboard stats load and show loading placeholders.
- [ ] Quick capture opens add-source modal.
- [ ] Graph spotlight renders and links to `/graph`.
- [ ] Recent activity refresh and link actions work.
- [ ] Ingestion/source cards render empty/loading/data states.

## Chat (`/chat`)
- [ ] Conversation list loads, creates, selects, deletes conversations.
- [ ] Message stream/loading state appears while sending.
- [ ] Citation rendering and source expansion work.
- [ ] Context panel appears on ultrawide and drawer on narrower screens.
- [ ] Composer send (`Enter`) and newline (`Shift+Enter`) behavior works.

## Notes (`/notes`)
- [ ] Notes and folders load on first render.
- [ ] Create, delete, pin, archive notes behave correctly.
- [ ] Folder create/delete and nested note list behavior works.
- [ ] Title/content autosave runs and save badge updates.
- [ ] `[[concept]]` extraction and right-panel linked concepts update.
- [ ] Add-as-insight extraction action works and reports result.

## Library (`/library`)
- [ ] Search, tab filtering, sort, and view mode toggles work.
- [ ] Add source modal (URL/file) success and error paths work.
- [ ] Card actions: open, delete, reprocess (when available).
- [ ] Empty/loading/list/grid states render correctly.

## Graph (`/graph`)
- [ ] Graph tree loads for authenticated users.
- [ ] Node center changes update sidebar context and adjacent nodes.
- [ ] Back navigation in graph view works.
- [ ] Filter panel relation/source/importance controls work.
- [ ] Auth-required empty state and error states render correctly.

## Settings (`/settings`)
- [ ] Theme preference control updates UI immediately.
- [ ] Sign out flow clears session and redirects to login.

## Auth (`/login`, `/signup`)
- [ ] Email/password login and signup success paths work.
- [ ] Form validation and error surfaces render correctly.
- [ ] Social auth buttons trigger provider flow.
- [ ] Navigation links between login/signup/home work.

## Landing (`/`)
- [ ] CTA buttons route to login and signup.
- [ ] Hero and panel design render in light and dark modes.
