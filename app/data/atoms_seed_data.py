"""Seed content for Atoms micro-learning modules."""

ATOMS_SEED = [
    {
        "title": "Frontend Developer",
        "description": (
            "Build modern web interfaces — from semantic HTML and responsive CSS "
            "to JavaScript interactivity and component-based UI development."
        ),
        "atoms": [
            {
                "title": "Semantic HTML Foundations",
                "sequence_order": 1,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# Why semantics matter\n\n"
                            "Screen readers, search engines, and future you all rely on "
                            "**meaningful tags** — not just `<div>` soup.\n\n"
                            "Use `<header>`, `<nav>`, `<main>`, `<article>`, and `<footer>` "
                            "to describe *what* content is, not just *how* it looks."
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "code",
                        "content_body": (
                            "<header>\n"
                            "  <nav aria-label=\"Primary\">\n"
                            "    <a href=\"/\">Breneo</a>\n"
                            "  </nav>\n"
                            "</header>\n"
                            "<main>\n"
                            "  <article>\n"
                            "    <h1>Frontend Developer</h1>\n"
                            "    <p>Build accessible interfaces.</p>\n"
                            "  </article>\n"
                            "</main>"
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "rich_text",
                        "content_body": (
                            "Pro tip: Pair semantic HTML with accessible attributes — "
                            "`alt` on images, `label` on form fields, and `aria-*` only "
                            "when native HTML cannot express the behavior."
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "To style elements with CSS classes only",
                        "To describe content meaning for browsers and assistive tech",
                        "To replace JavaScript event handlers",
                    ],
                    "correct_index": 1,
                    "explanation": (
                        "Semantic HTML communicates structure and meaning, improving "
                        "accessibility, SEO, and maintainability."
                    ),
                },
            },
            {
                "title": "CSS Flexbox for Layouts",
                "sequence_order": 2,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# Flexbox in 60 seconds\n\n"
                            "Flexbox aligns items along a **main axis** (row or column) "
                            "and a **cross axis** perpendicular to it.\n\n"
                            "Parent = flex container. Children = flex items."
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "code",
                        "content_body": (
                            ".card-row {\n"
                            "  display: flex;\n"
                            "  justify-content: space-between;\n"
                            "  align-items: center;\n"
                            "  gap: 1rem;\n"
                            "}"
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "markdown",
                        "content_body": (
                            "**Common patterns**\n\n"
                            "- Navbar: `justify-content: space-between`\n"
                            "- Centered hero: `justify-content: center; align-items: center`\n"
                            "- Equal columns: `flex: 1` on each child"
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "`align-items` controls alignment along the cross axis",
                        "`justify-content` controls font size",
                        "`flex-direction` only accepts `column`",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "`align-items` aligns flex items along the cross axis; "
                        "`justify-content` aligns along the main axis."
                    ),
                },
            },
            {
                "title": "JavaScript DOM Interactions",
                "sequence_order": 3,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# The DOM bridge\n\n"
                            "The **Document Object Model** is the browser's live tree of your page. "
                            "JavaScript can select nodes, listen for events, and update content "
                            "without a full reload."
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "code",
                        "content_body": (
                            "const btn = document.querySelector('#save');\n"
                            "const status = document.querySelector('#status');\n\n"
                            "btn.addEventListener('click', () => {\n"
                            "  status.textContent = 'Saved!';\n"
                            "});"
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "rich_text",
                        "content_body": (
                            "Prefer `querySelector` for flexibility, delegate events when "
                            "lists are dynamic, and always clean up listeners in SPAs "
                            "to avoid memory leaks."
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "`addEventListener` attaches a handler to a DOM event",
                        "`innerHTML` is the only way to update text safely",
                        "The DOM is a CSS stylesheet object",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "`addEventListener` registers callbacks for events like `click`, "
                        "`input`, or `keydown` on DOM nodes."
                    ),
                },
            },
            {
                "title": "React Components & Props",
                "sequence_order": 4,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# Components = reusable UI\n\n"
                            "React apps are trees of **components** — functions that return "
                            "JSX describing what should appear on screen.\n\n"
                            "Props pass data *into* a component; state holds data *inside* it."
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "code",
                        "content_body": (
                            "function SkillBadge({ name, level }) {\n"
                            "  return (\n"
                            "    <span className=\"badge\">\n"
                            "      {name} · {level}\n"
                            "    </span>\n"
                            "  );\n"
                            "}\n\n"
                            "// Usage:\n"
                            "// <SkillBadge name=\"TypeScript\" level=\"Intermediate\" />"
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "markdown",
                        "content_body": (
                            "**Rules of thumb**\n\n"
                            "1. Keep components small and focused\n"
                            "2. Lift shared state to the nearest common parent\n"
                            "3. Never mutate props — treat them as read-only"
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "Props are read-only inputs passed from parent to child",
                        "Props are global variables shared across all tabs",
                        "Props replace the need for HTML entirely",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "Props flow one way (parent → child) and should not be modified "
                        "by the receiving component."
                    ),
                },
            },
        ],
    },
    {
        "title": "UI/UX Designer",
        "description": (
            "Design human-centered digital experiences — research users, structure flows, "
            "prototype interfaces, and craft clear visual systems."
        ),
        "atoms": [
            {
                "title": "Design Thinking Overview",
                "sequence_order": 1,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# Design thinking loop\n\n"
                            "Great UX is not decoration — it's **problem solving**.\n\n"
                            "The classic loop:\n"
                            "1. **Empathize** — understand users\n"
                            "2. **Define** — frame the right problem\n"
                            "3. **Ideate** — explore solutions\n"
                            "4. **Prototype** — make ideas tangible\n"
                            "5. **Test** — learn and iterate"
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "rich_text",
                        "content_body": (
                            "At Breneo, design thinking helps you connect learner goals "
                            "to interface decisions — every screen should answer: "
                            "What is the user trying to accomplish right now?"
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "markdown",
                        "content_body": (
                            "**Watch out for**\n\n"
                            "- Jumping to high-fidelity mockups too early\n"
                            "- Designing for yourself instead of real users\n"
                            "- Treating research as a one-time phase"
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "Empathize → Define → Ideate → Prototype → Test",
                        "Sketch → Ship → Ignore feedback",
                        "Research → Build → Never iterate",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "Design thinking is iterative: empathize with users, define the problem, "
                        "ideate solutions, prototype, and test."
                    ),
                },
            },
            {
                "title": "User Research Methods",
                "sequence_order": 2,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# Qualitative vs quantitative\n\n"
                            "**Qualitative** (interviews, usability tests) tells you *why*.\n\n"
                            "**Quantitative** (surveys, analytics) tells you *how many*.\n\n"
                            "Use both — numbers spot patterns; conversations reveal motivations."
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "rich_text",
                        "content_body": (
                            "A 30-minute moderated usability test with 5 users often surfaces "
                            "80% of major usability issues. Prepare tasks, stay neutral, "
                            "and note where users hesitate or misclick."
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "markdown",
                        "content_body": (
                            "**Research deliverables**\n\n"
                            "- Personas (based on real data, not fiction)\n"
                            "- Journey maps (steps, pain points, opportunities)\n"
                            "- Problem statements: *As a [user], I need [goal] so that [outcome]*"
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "Usability testing reveals why users struggle with a flow",
                        "Analytics alone always explain user motivation",
                        "Personas should be invented for aesthetic decks",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "Moderated usability tests observe behavior and uncover friction; "
                        "they complement analytics with qualitative insight."
                    ),
                },
            },
            {
                "title": "Wireframes & Prototypes",
                "sequence_order": 3,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# Fidelity ladder\n\n"
                            "**Low-fi wireframes** — layout and hierarchy, grey boxes, fast.\n\n"
                            "**Mid-fi** — real copy, basic components.\n\n"
                            "**High-fi prototypes** — visual design + interaction for testing."
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "rich_text",
                        "content_body": (
                            "Start low-fi to align on structure before pixels. "
                            "Tools like Figma let you link frames into clickable flows "
                            "so stakeholders experience the journey, not just static screens."
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "markdown",
                        "content_body": (
                            "**Annotation tips**\n\n"
                            "- Label primary vs secondary actions\n"
                            "- Note empty, loading, and error states\n"
                            "- Mark responsive breakpoints when layout shifts"
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "Low-fi wireframes focus on structure before visual polish",
                        "High-fi mockups should always come first",
                        "Prototypes cannot include user flows",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "Low-fidelity wireframes validate information architecture and layout "
                        "cheaply before investing in visual design."
                    ),
                },
            },
            {
                "title": "Visual Hierarchy & Typography",
                "sequence_order": 4,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# Guide the eye\n\n"
                            "Hierarchy uses **size, weight, color, and spacing** to show "
                            "what matters most.\n\n"
                            "One primary action per screen. Supporting content recedes visually."
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "code",
                        "content_body": (
                            "/* Type scale example */\n"
                            "h1 { font-size: 2rem; font-weight: 700; }\n"
                            "h2 { font-size: 1.5rem; font-weight: 600; }\n"
                            "body { font-size: 1rem; line-height: 1.5; }\n"
                            "caption { font-size: 0.875rem; color: #64748b; }"
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "rich_text",
                        "content_body": (
                            "Limit typefaces (often 1–2 families), maintain consistent line height "
                            "(1.4–1.6 for body), and ensure contrast ratios meet WCAG AA "
                            "(4.5:1 for normal text)."
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "Visual hierarchy helps users scan and prioritize content",
                        "All text should be the same size for fairness",
                        "Contrast guidelines only apply to print design",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "Hierarchy directs attention to primary actions and headings; "
                        "accessible contrast ensures readability for all users."
                    ),
                },
            },
        ],
    },
    {
        "title": "Product Owner",
        "description": (
            "Own the product vision and backlog — translate business goals into actionable "
            "user stories, prioritize value, and keep stakeholders aligned."
        ),
        "atoms": [
            {
                "title": "Agile & Scrum Essentials",
                "sequence_order": 1,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# Scrum in one sprint\n\n"
                            "Scrum delivers value in **time-boxed sprints** (often 2 weeks).\n\n"
                            "Key roles:\n"
                            "- **Product Owner** — maximizes product value\n"
                            "- **Scrum Master** — enables the process\n"
                            "- **Developers** — build the increment"
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "rich_text",
                        "content_body": (
                            "Ceremonies: Sprint Planning, Daily Scrum, Sprint Review, "
                            "Retrospective. Artifacts: Product Backlog, Sprint Backlog, Increment. "
                            "The PO owns the *what* and *why*; the team owns the *how*."
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "markdown",
                        "content_body": (
                            "**PO mindset**\n\n"
                            "Say *no* with clarity. Protect the team from scope churn. "
                            "Keep the backlog ordered by value, not by who shouted loudest."
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "The Product Owner prioritizes the backlog to maximize value",
                        "The Product Owner writes all production code",
                        "Sprints have no fixed time box in Scrum",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "The Product Owner is accountable for ordering the Product Backlog "
                        "and ensuring the team works on the highest-value items."
                    ),
                },
            },
            {
                "title": "Writing Effective User Stories",
                "sequence_order": 2,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# User story template\n\n"
                            "**As a** [persona],\n"
                            "**I want** [capability],\n"
                            "**So that** [benefit].\n\n"
                            "Add **acceptance criteria** — the conditions of done."
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "code",
                        "content_body": (
                            "Story:\n"
                            "As a job seeker, I want to save courses\n"
                            "so that I can review them later.\n\n"
                            "Acceptance criteria:\n"
                            "- Heart icon toggles saved state\n"
                            "- Saved courses appear on /saved\n"
                            "- State persists after refresh"
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "rich_text",
                        "content_body": (
                            "INVEST checklist: Independent, Negotiable, Valuable, Estimable, "
                            "Small, Testable. Split epics vertically (end-to-end slices), "
                            "not horizontally (all UI, then all API)."
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "Acceptance criteria define when a story is complete",
                        "User stories should never mention the user benefit",
                        "Bigger stories are always better for velocity",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "Acceptance criteria make stories testable and align the team "
                        "on expected behavior before development starts."
                    ),
                },
            },
            {
                "title": "Prioritization Frameworks",
                "sequence_order": 3,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# MoSCoW & RICE\n\n"
                            "**MoSCoW**: Must, Should, Could, Won't (this release).\n\n"
                            "**RICE** score = (Reach × Impact × Confidence) / Effort.\n\n"
                            "Pick a framework; be transparent about trade-offs."
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "math_formula",
                        "content_body": "RICE = (Reach × Impact × Confidence) / Effort",
                    },
                    {
                        "card_index": 2,
                        "content_type": "markdown",
                        "content_body": (
                            "**Practical tips**\n\n"
                            "- Re-prioritize when new data arrives\n"
                            "- Balance tech debt with features\n"
                            "- Tie priorities to OKRs or north-star metrics"
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "RICE divides Reach × Impact × Confidence by Effort",
                        "MoSCoW ranks items by programming language",
                        "Prioritization should never change mid-quarter",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "RICE helps compare initiatives objectively; higher scores suggest "
                        "more value per unit of effort."
                    ),
                },
            },
            {
                "title": "Stakeholder Communication",
                "sequence_order": 4,
                "content_cards": [
                    {
                        "card_index": 0,
                        "content_type": "markdown",
                        "content_body": (
                            "# Translate, don't transmit\n\n"
                            "Stakeholders care about **outcomes** (revenue, retention, risk). "
                            "Teams care about **output** (features, bugs fixed).\n\n"
                            "Your job: bridge both with clarity and evidence."
                        ),
                    },
                    {
                        "card_index": 1,
                        "content_type": "rich_text",
                        "content_body": (
                            "Sprint Review demo > status email. Show working software, "
                            "share metrics, acknowledge trade-offs. When saying no, "
                            "offer alternatives: scope cut, date shift, or phased delivery."
                        ),
                    },
                    {
                        "card_index": 2,
                        "content_type": "markdown",
                        "content_body": (
                            "**Communication toolkit**\n\n"
                            "- Roadmap (now / next / later)\n"
                            "- Release notes for users\n"
                            "- Decision log (what, why, date) for audit trail"
                        ),
                    },
                ],
                "quiz_data": {
                    "options": [
                        "Link decisions to outcomes stakeholders care about",
                        "Share only technical jargon to build credibility",
                        "Avoid documenting decisions to stay agile",
                    ],
                    "correct_index": 0,
                    "explanation": (
                        "Effective PO communication frames product decisions in terms of "
                        "business outcomes and user value, backed by data when possible."
                    ),
                },
            },
        ],
    },
]
