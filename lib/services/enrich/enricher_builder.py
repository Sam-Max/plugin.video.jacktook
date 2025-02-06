from typing import List, Optional
from lib.domain.interface.enricher_interface import EnricherInterface
from collections import defaultdict
from lib.domain.source import Source


class EnricherBuilder:
    def __init__(self):
        self._enrichers: List[EnricherInterface] = []

    def add(self, enricher: Optional[EnricherInterface]) -> "EnricherBuilder":
        if enricher is None:
            return self

        self._enrichers.append(enricher)
        return self

    def build(self, items: List[Source]) -> List[Source]:
        processed = []
        for enricher in self._enrichers:
            enricher.initialize(items)

        for item in [item.copy() for item in items]:
            for enricher in self._enrichers:
                enricher.enrich(item)
            processed.append(item)
        return processed

    def generate_report(self) -> str:
        report = []
        enrichers_info = []
        provided_fields = defaultdict(list)
        all_needs = set()

        for enricher in self._enrichers:
            name = type(enricher).__name__
            needs = enricher.needs()
            provides = enricher.provides()
            enrichers_info.append((name, needs, provides))
            all_needs.update(needs)
            for field in provides:
                provided_fields[field].append(name)

        # Enrichers Details Section
        report.append("Enrichers Report:")
        report.append("=================")
        report.append("\nEnrichers Details:")
        for name, needs, provides in enrichers_info:
            report.append(f"- {name}:")
            report.append(f"  Needs: {', '.join(needs) if needs else 'None'}")
            report.append(f"  Provides: {', '.join(provides) if provides else 'None'}")
            report.append("")

        # Insights Section
        report.append("\nInsights:")
        report.append("=========")

        # Insight 1: Check unmet dependencies
        cumulative_provided = set()
        insights_unmet = []
        for index, (name, needs, _) in enumerate(enrichers_info):
            unmet = [field for field in needs if field not in cumulative_provided]
            if unmet:
                insights_unmet.append((name, unmet))
            # Update cumulative_provided with current enricher's provides
            cumulative_provided.update(enrichers_info[index][2])

        if insights_unmet:
            report.append(
                "\n1. Enrichers with unmet dependencies (needs not provided by prior enrichers):"
            )
            for name, unmet in insights_unmet:
                report.append(
                    f"   - {name} requires fields not provided earlier: {', '.join(unmet)}"
                )
        else:
            report.append(
                "\n1. All enrichers' dependencies are met by prior enrichers."
            )

        # Insight 2: Check overlapping provided fields
        multi_provided = [
            field for field, providers in provided_fields.items() if len(providers) > 1
        ]
        if multi_provided:
            report.append(
                "\n2. Fields provided by multiple enrichers (possible conflicts):"
            )
            for field in multi_provided:
                providers = ", ".join(provided_fields[field])
                report.append(f"   - Field '{field}' is provided by: {providers}")
        else:
            report.append("\n2. No fields are provided by multiple enrichers.")

        # Insight 3: Check unused provides
        unused_provides = defaultdict(list)
        for i, (name, _, provides) in enumerate(enrichers_info):
            for field in provides:
                used = False
                for j in range(i + 1, len(enrichers_info)):
                    if field in enrichers_info[j][1]:
                        used = True
                        break
                if not used:
                    unused_provides[name].append(field)

        if unused_provides:
            report.append(
                "\n3. Fields provided but not needed by subsequent enrichers:"
            )
            for name, fields in unused_provides.items():
                report.append(f"   - {name} provides: {', '.join(fields)}")
        else:
            report.append("\n3. All provided fields are used by subsequent enrichers.")

        return "\n".join(report)
