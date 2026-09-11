---
block: requirements
difficulty: practice
id: system-analyst-requirements-04-en
kind: question
subblock: elicitation
tags:
- requirements
- stakeholders
title: Interviewing a stakeholder
topic: interview
weight: 1
---

## Question
How do you prepare for and run a stakeholder interview so that you come away with requirements rather than a wish list?

## Answer
Preparation matters more than the meeting itself: before the interview, the analyst studies the domain, the existing system, and the documents so as not to waste someone else's hour on things that can be read, and comes with hypotheses rather than a blank page.

Meeting structure:
- **Goal and scope** — state out loud what we're discussing and what the output will be, so the conversation doesn't sprawl.
- **Open questions about current work** — "show me how you do this today", "what's the most annoying part of it". People describe their pain well and the solution they need poorly.
- **Clarifying with numbers** — "how often", "how long does it take", "what happens if". Numbers separate a real problem from an occasional annoyance.
- **Probing edge cases** — what if there's no data, if the customer changed their mind, if something arrived twice.

The key technique is **digging for the need behind the proposed solution**. When you hear "we need an Export to Excel button", ask "what do you do with that file next": it often turns out the person needs a filtered report and named Excel because they didn't know any other way.

End the interview by paraphrasing what you heard in your own words while the stakeholder is still there — that way misunderstandings surface immediately rather than at the demo. Within the day, send out a written summary with decisions and open questions and ask for confirmation: this is the first requirements artifact.
