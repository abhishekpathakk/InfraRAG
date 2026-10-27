# Tips for writing tutorials

## Learning objectives

* Provide multiple ways to engage with key topics.
* Encourage critical thinking.  Explain the reasoning behind a methodology.  Say why, not just what.

## Purpose

This collection of tips aims to help enrich understanding and retention by give participants multiple ways of interacting with the core content.

Adding elements to support different styles of engagement on key topics helps reinforce those topics (e.g. through hands-on practice,
group discussion, recorded walk-through, etc.) and encourages exploring core concepts and relationships (e.g. revisiting diagrams and
demo results as new related content is progressively introduced).

Ultimately the goal is to give participants exposure and retention to new skills and knowledge that aids them in practical ways.
Enriching a tutorial with multiple ways of interacting with the content helps more participants synthesize the main take-aways.

## Tips for helping participants to engage with the content

> We learn best as we seek solutions to problems. When you cover a particular topic, start with defining and describing
> a particular problem or challenge before you start talking about ways to solve that problem.
>
> -- [How to Teach Adults](https://sec.eff.org/articles/how-to-teach-adults)

* Explicitly list the **learning objectives** for the tutorial.
  * This helps the participants know in advance what they can expect to gain and whether or not this is what they are looking for.
  * This also helps keep the content focused.  We can ask reviewers to check that the content sticks to the objectives and covers each one adequately.
  * To be clear and concise, we must make assumptions about what experience and knowledge our audience already has.  Stating learning objectives communicates those assumptions.
  * It also might help to explicitly state what is *out of scope* for the tutorial or what concepts someone should *know before starting*.
* **Concisely describe the problem** to be solved before delving into a solution.
  * Using a problem-oriented presentation style supports engagement by explaining the motivations, providing a context, and
    inviting participants to think critically and apply problem solving skills.
  * Anchoring the content to a tangible practical outcome ties the narrative thread together into a tidy story, which again
    helps with engagement by keeping the content focused on a well-defined scope.
* Include **diagrams** to illustrate and summarize the key points.
  * Diagrams, graphs, and other illustrations invite a **non-linear exploration** of the concepts, relationships, or behaviors being presented.
* **Demonstrate** a concrete example of the concepts being presented.
  * Demos convey a wealth of implicit information.  They give everyone a shared context and can efficiently bridge gaps and resolve hidden assumptions.
  * Written demos are searchable and easier to update.  Recorded screencasts provide a richer context, especially when using graphical interfaces.
* Provide **repeatable steps** for participants who want to follow along with the demo, or give **practice exercises** for follow-up.
  * Exercises and repeatable demos provide the basis for hands-on exploratory learning.
  * Documenting repeatable demo steps also supports future updates to the tutorial, to keep the content fresh and relevant.
* Focus on **sharing skills and concepts**, not just tools.
  * Sometimes it does help to have a short introductory demo of just how to use a specific tool in a specific context.
    If that is valuable, go for it!  But if the tool's own documentation is sufficient, consider just citing it.
  * Learning new skills and techniques tend to be more helpful in the long term than learning how to use a single specific tool.
    Tools have a shorter lifespan than careers.
* **Annotate your citations.**
  * When suggesting additional material (such as a "See Also" section), briefly explain why this reference is relevant/related and what the reader can expect to gain.

## Tips for demos (whether textual or recorded)

* **Describe a specific challenge.**
  * Start with the motivational hook.  Why is this topic important and relevant to the reader?  How will learning this help them?
  * Answer what problem we are solving before delving into the solution space.
* For conceptual tutorials: **Show how to observe the key behaviors being described.**
  * Use diagrams and illustrations to summarize the concepts.
  * Choose an existing concrete system that is relevant to the audience and show how to observe either the concepts themselves or their indirect effects.
  * When demonstrating complex interactions, it may help to first demo simpler scenarios in an isolated artificial environment.
    * Example: queuing behavior when all incoming jobs are equally expensive and arrive at a stable predictable rate
* For technique demonstrations: **Show how and explain the reasoning.**
  * Show enough detail (screenshots, command output) that the reader can see what you are describing.
  * Explicitly highlight the relevant parts of the output (e.g. doodle on screenshots) if it helps clarity.
  * Explain what each step teaches us, how it relates to the problem we are solving.
* **Explicitly state key assumptions.**
  * This helps clarify scope and also encourages readers to question and compare their own assumptions.
* **Invite critical thinking**
  * Example: Demonstrate the usefulness of a technique through a problem-solving story (but keep the focus on the technique, and trim the story to its relevant essentials).
  * Example: List some pros and cons of an approach, or show contrasting cases where one method works better than another.
  * When different ways of evaluating the results can lead to different insights or interpretations, highlight this.  Offer tips for how to draw useful conclusions.
  * Lead the participants to a successful conclusion, to reward their investment of time and attention.  Leading to false or ambiguous conclusions discourages users.
* **Big picture before caveats and variants.**
  * Finish narating the normal clean use-case before delving into caveats, gotchas, and variants of the technique.
  * This gives the reader the completed big picture before introducing wrinkles, which is especially helpful for readers who are new to the topic.
* **Quick reference / cheat sheet**
  * To support returning visitors, include a quick reference section with a terse summary of steps or commands.
  * Include enough context to support a user who does not have time to re-read any other section.
* **Summarize key points.**
  * Conclude with a summary of key points that ties the presented content back to the learning objectives.
  * This may include:
    * the generic problem for which the technique is useful
    * how the technique helps address the problem
    * the reasoning behind the method
    * caveats that can give misleading results

## Summary

This guide outlined tips along with their underlying motivations for writing tutorials that maintain a clear explicit focus,
provide multiple ways to engage with the core topics, and support quick refreshers for returning participants.
