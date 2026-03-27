"""
HalfFull project configuration.
Stub version for eval pipeline compatibility.
"""

# Frozen list of condition IDs supported by HalfFull models
CONDITION_IDS: list[str] = [
    "perimenopause",
    "hypothyroidism",
    "kidney_disease",
    "sleep_disorder",
    "anemia",
    "iron_deficiency",
    "hepatitis",
    "prediabetes",
    "inflammation",
    "electrolyte_imbalance",
    "vitamin_b12_deficiency",
    "vitamin_d_deficiency",
]

# MedGemma API configuration
MEDGEMMA_ENDPOINT_URL: str = "http://localhost:8080"  # Override with Colab tunnel URL
MEDGEMMA_TIMEOUT_SECONDS: int = 30
