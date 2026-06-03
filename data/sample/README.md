# Synthetic Sample Items

This directory holds **illustrative synthetic items** that demonstrate the CBLRE item format. These items:

- Are **not part of the CBLRE scoring set**
- Are not expert-reviewed and carry no legal or factual authority
- Do not represent real legal scenarios accurately
- Exist only to show what a valid item looks like before you write your own

Do not draw any conclusions about benchmark difficulty or model performance from these items.

---

## Adding items

Add 2–3 synthetic items per track as `.json` files or as a single `sample.jsonl`. Every item must conform to [`schema/eval_item.schema.json`](../../schema/eval_item.schema.json).

Mark every synthetic item with:
- `"source": "synthetic-illustrative"` in the `provenance` block
- `"canary": "SAMPLE-ITEM-NOT-IN-SCORING-SET"` so there is no ambiguity

---

## Minimal example (MCQ)

```json
{
  "id": "sample-mcq-common-law-001",
  "track": "common_law",
  "language": "en",
  "parity_group": null,
  "difficulty": "core",
  "jurisdiction": "ON",
  "format": "mcq",
  "prompt": "Under Canadian common law, which elements must a plaintiff establish to succeed in a negligence claim? [SYNTHETIC — NOT A SCORING ITEM]",
  "system": null,
  "context": null,
  "tools": null,
  "choices": [
    "(A) Duty of care, breach, causation, and damage",
    "(B) Faute, préjudice, and lien de causalité",
    "(C) Offer, acceptance, and consideration",
    "(D) Intention, act, and harm"
  ],
  "scoring": {
    "method": "mcq_exact",
    "answer": "A",
    "rubric_id": null,
    "reference": null,
    "must_include": [],
    "must_not_include": [],
    "valid_citations": [],
    "expected_refusal": null,
    "expected_tool": null,
    "expected_args": null
  },
  "provenance": {
    "author": "synthetic",
    "validated_by": null,
    "review_date": null,
    "source": "synthetic-illustrative",
    "canary": "SAMPLE-ITEM-NOT-IN-SCORING-SET"
  }
}
```

## Minimal example (open / rubric)

```json
{
  "id": "sample-open-qc-civil-001",
  "track": "quebec_civil_law",
  "language": "fr",
  "parity_group": null,
  "difficulty": "applied",
  "jurisdiction": "QC",
  "format": "open",
  "prompt": "Expliquez les trois éléments de la responsabilité civile extracontractuelle en droit québécois. [SYNTHÉTIQUE — PAS UN ITEM DE NOTATION]",
  "system": null,
  "context": null,
  "tools": null,
  "choices": null,
  "scoring": {
    "method": "rubric",
    "answer": null,
    "rubric_id": "qc-civil-liability-v1",
    "reference": "Art. 1457 C.c.Q. : la faute, le préjudice, et le lien de causalité.",
    "must_include": [],
    "must_not_include": [],
    "valid_citations": ["art. 1457 C.c.Q."],
    "expected_refusal": null,
    "expected_tool": null,
    "expected_args": null
  },
  "provenance": {
    "author": "synthetic",
    "validated_by": null,
    "review_date": null,
    "source": "synthetic-illustrative",
    "canary": "SAMPLE-ITEM-NOT-IN-SCORING-SET"
  }
}
```
