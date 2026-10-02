# Create a specification from Assistant chat

For the complete creation/edit/switch/close rules and edge cases, see the
[document lifecycle state machines](assistant-document-lifecycle.md).

In a browser Assistant chat, ask for a new specification. You can include its
design requirements in the same message, for example: “Create a new spec
document for a 3-bit comparator with two 3-bit inputs and three 1-bit result
outputs.” Contentful requests first present an architecture review with interfaces,
clocks/reset, rationale, assumptions and concrete configuration. Approve, revise or
cancel it; essential questions require revision. The accepted review ID and
architecture transfer into the new chat. After architecture approval, automatic
owners create the package and continue without a final-save confirmation.
Restricted owners show a creation card: review or edit **Name**, then select
**Create specification and continue**. If several Spec services
are configured, the card can select one. The destination is always
derived from the name under `SPEC_DOCUMENT_ROOT`, for example
`Timer controller` becomes `timer-controller.spec`. Filename collisions receive
readable numbers. The owner generates and reserves the internal identity and
destination independently. Display renames preserve the saved path; see
[naming and identifiers](naming-and-identifiers.md).

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
such as `[2:0]` to the Spec API's compact `2:0` syntax. The architecture review keeps
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
overwritten. Correct a rejected name or retry an offline service. Once creation
has started, replay its original request to recover the reserved destination;
changing the name requires a new request.

Creating a package makes it the service's visible document. Existing chats use
their persistent `owner_document_key` and can continue refining the original
package without reopening it. Copies with equal document IDs have separate
bindings. Choose the appropriate service when several are available.

The browser creation tool is available to root chats in all three presets,
including unbound chats. Headless requests and standing read-only specialists do
not receive it. The new package itself is created through the existing Spec
`POST /documents/create` endpoint. The Assistant's
`POST /spec2gds-api/sources/create` endpoint also supports the existing
new-conversation chooser; card requests add a persisted creation-request ID
to resume safely after partial success.


## Creation blocked after architecture preparation

`prepare_architecture_review` prepares a review; it does not approve it.
Contentful creation requires human approval and `architecture_review_id` from
that approved review. The unbound-chat prompt and creation tool description
state this order explicitly. Only an explicitly empty package may skip review.

The chat footer previously selected only the latest tool result in a turn.
A premature creation call could therefore replace the architecture approval
card with “Specification creation unavailable,” leaving no visible way to
approve it. The footer now retains each distinct architecture review alongside
the latest result, including creation errors. It still fetches durable review
status, and approval continues through the existing server decision endpoint.

After rebuilding and restarting the assistant, reload the affected chat,
approve the intended architecture card, and continue with its displayed review number.
If preparation itself failed, inspect the tool result and resolve that error
before preparing another review. Existing conversation history is preserved.

Validation (from `ai-assistant/` using the supported Node runtime):
`npm test`, `npm run typecheck`, and `npm run build`. All 119 assistant tests
pass. Running the suite through `npm --prefix` can conflict with nvm in the
setup test; run `npm test` from the assistant directory instead.
