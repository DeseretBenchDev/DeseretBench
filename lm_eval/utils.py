"""Helper functions for the lm-evaluation-harness DeseretBench MC task."""

LETTERS = "ABCDEFGH"  # match deseretbench.schema.LETTERS


def doc_to_text(doc) -> str:
    lines = [doc["question"], ""]
    for i, c in enumerate(doc["choices"]):
        lines.append(f"{LETTERS[i]}. {c}")
    lines.append("")
    lines.append("Think it through if helpful, then end with a line exactly: ANSWER: <letter>")
    return "\n".join(lines)


def doc_to_target(doc) -> str:
    return LETTERS[int(doc["answer_index"])]
