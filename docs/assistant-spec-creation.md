# Create a specification from Assistant chat

In a browser Assistant chat, ask for a new specification. You can include its
design requirements in the same message, for example: “Create a new spec
document for a 3-bit comparator with two 3-bit inputs and three 1-bit result
outputs.” Automatic owners create the package and continue without confirmation.
Restricted owners show a creation card: review or edit the title and document
ID, then select **Create specification and continue**. If several Spec services
are configured, the card can select one. The destination is always
`SPEC_DOCUMENT_ROOT/<documentId>.spec`.

The Spec API creates and activates the empty package. The Assistant creates a
new document-bound chat with the same execution preset and submits the
original request there. The old chat remains open and keeps its original
binding. The new chat's content submissions follow the owner's policy: validated
automatic save by default, or details and explicit proposal review under
`--require-human-approval`. Missing required values still request clarification.
For an empty specification request, the new chat
can finish with the package ready.

For a new component proposal, the Assistant supplies an empty `instances` array
when there are no initial design instances and converts HDL-style wire ranges
such as `[2:0]` to the Spec API's compact `2:0` syntax. The details card keeps
input and output widths separate when they differ. A rejected review remains
unapplied; ask the Assistant to prepare a new proposal after correcting the
cause, then inspect its new review card.

Creation receipts survive a page reload. **Cancel** works before restricted
creation starts. If a package was saved but chat setup failed, retry resumes
chat setup without creating another package. Automatic saved receipts continue
the document chat without confirmation. The card offers **Refresh** to check
progress. New owners advertise durable creation receipts: an uncertain response
can be recovered with the same request ID and exact saved details. Older owners
retain the uncertain status and do not repeat the call; inspect the displayed
destination before making another request. Existing destinations are never
overwritten. Correct a rejected document ID or retry an offline service.

Creating a package makes it the service's visible document. Existing chats use
their persistent `owner_document_key` and can continue refining the original
package without reopening it. Copies with equal document IDs have separate
bindings. Choose the appropriate service when several are available.

The browser creation tool is available to root chats in all three presets,
including unbound chats. Headless requests and delegated analysis children do
not receive it. The new package itself is created through the existing Spec
`POST /documents/create` endpoint. The Assistant's
`POST /spec2gds-api/sources/create` endpoint also supports the existing
new-conversation chooser; card requests add a persisted creation-request ID
to resume safely after partial success.
