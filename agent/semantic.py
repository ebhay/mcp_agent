"""Embedding-based intent matching for incoming mail."""
import math

from openai import OpenAI

INTENTS = {
    "create_batch": "Request to create a new training batch or cohort with trainee count, required skills, and start and end dates",
    "unallocated": "Cohort that is unallocated or unassigned and still needs a trainer",
}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


class IntentMatcher:
    def __init__(self, client: OpenAI, model: str, threshold: float):
        self.client = client
        self.model = model
        self.threshold = threshold
        names = list(INTENTS)
        vectors = self._embed([INTENTS[n] for n in names])
        self.intent_vectors = dict(zip(names, vectors))

    def _embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def match(self, text: str) -> str | None:
        """Returns the best intent label if it clears the threshold, else None."""
        vector = self._embed([text[:4000]])[0]
        scored = {name: _cosine(vector, v) for name, v in self.intent_vectors.items()}
        best = max(scored, key=scored.get)
        return best if scored[best] >= self.threshold else None
