# Reference data

| File | What | Source | License |
|---|---|---|---|
| `census1990_first_names.txt` | 5,163 US first names (female + male lists merged, lower-case, one per line) | US Census Bureau, 1990 Census name frequencies: `dist.female.first`, `dist.male.first` (https://www2.census.gov/topics/genealogy/1990surnames/) | Public domain (US Government work) |
| `census1990_surnames.txt` | Most frequent US surnames (lower-case), covering ~81% of the population. The download was cut off partway, so the list is truncated rather than complete. | Same source, `dist.all.last` | Public domain |

Used by `customer_category_audit.py` to recognise customers whose name is a
person's (D-119). A first-name match is the main clue; a surname match only
supports it.
