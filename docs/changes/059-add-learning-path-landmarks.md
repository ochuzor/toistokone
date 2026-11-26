# Add learning-path landmarks

## Problem

Practice currently presents useful cards and grammar tips, but it does not
introduce a learner to a course, learning path, or newly reached topic.

## Desired behavior

Use unobtrusive instructional cards as landmarks in an ongoing practice stream:
a welcome when a learner begins a path, followed by brief introductions for
learning sets. Each landmark should offer quick help and a fuller detail page,
like grammar guides.

## Proposed scope

- Add authorable path and learning-set teaching content, likely Markdown.
- Persist which landmarks a learner has acknowledged independently of card
  progress.
- Show an acknowledgement card before the next queued practice question, then
  retain compact access to its guidance.

## Open product decisions

- How a learner explicitly starts, changes, or leaves an active learning path.
- Whether starting a path automatically activates its currently available set.
- Whether a set introduction appears on activation, unlock, or set-page visit.
- The final Markdown metadata and validation rules for landmark content.

## Constraints

Do not change quiz selection, scores, mastery, or current learning-set behavior
until the path-activation model is agreed.

## Status

Pending — intentionally deferred for further product design.
