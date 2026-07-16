default_params = {
    "tax_brackets": {
        "all": [
            {"income_up_to": 25_000, "rate": 0.1},
            {"income_up_to": 50_000, "rate": 0.2},
            {"income_up_to": 75_000, "rate": 0.3},
            {"income_up_to": 100_000, "rate": 0.4},
            {"income_up_to": float("inf"), "rate": 0.5},
        ],
        "zzp": [
            {"income_up_to": 15_000, "rate": 0},
            {"income_up_to": 25_000, "rate": 0.1},
            {"income_up_to": 50_000, "rate": 0.2},
            {"income_up_to": 75_000, "rate": 0.3},
            {"income_up_to": 100_000, "rate": 0.4},
            {"income_up_to": float("inf"), "rate": 0.5},
        ],
    },
    "zvw_benefit": {
        "zt_a": 1_500,
        "ztafb": 0.15,
        "wml": 30_000,
        "wml_couple": 60_000,
        "zt_p": 2_250,
        "verm": 0,
        "verm_p": 0,
        "ztmaxv_a": 140213,
        "ztmaxv_p": 177301,
        "htmaxv": 114000,
        "ztmin": 24,
    },
    "child_benefits": [
        {"age_up_to": 6, "benefit": 800},
        {"age_up_to": 12, "benefit": 800},
        {"age_up_to": 18, "benefit": 800},
    ],
}
