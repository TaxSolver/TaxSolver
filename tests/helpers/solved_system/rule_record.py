from dataclasses import dataclass
from typing import Optional


@dataclass
class RuleRecord:
    name: str
    var_name: list[str]
    family: str
    type: str
    rate: float
    b: int
    weight: int
    bracket_start: Optional[float] = None
    bracket_end: Optional[float] = None
    target_var: Optional[str] = None

    @classmethod
    def from_rule(cls, rule):
        return cls(
            name=rule.name,
            var_name=rule.var_name,
            family=rule.metadata.get("family", rule.name),
            type=rule.__class__.__name__,
            rate=rule.tx.backend.get_value(rule.rate),
            b=rule.tx.backend.get_value(rule.b),
            bracket_start=rule.bracket_start
            if hasattr(rule, "bracket_start")
            else None,
            bracket_end=rule.bracket_end if hasattr(rule, "bracket_end") else None,
            target_var=rule.target_var if hasattr(rule, "target_var") else None,
            weight=rule.weight,
        )

    @classmethod
    def from_rules_and_rates_table(cls, df):
        for i, row in df.iterrows():
            yield cls(
                name=row["rule_name"],
                var_name=row["var_name"].split(":"),
                family=row["rule_family"],
                type=row["rule_type"],
                rate=row["rate"],
                b=row["b"],
                bracket_start=row["bracket_start"],
                bracket_end=row["bracket_end"],
                weight=row["weight"] if row.get("weight", None) else 1,
                target_var=row["target_var"]
                if row.get("target_var", None)
                else "income_before_tax",
            )

    def __repr__(self):
        return f"{self.name} - {self.family}: {self.rate}"
