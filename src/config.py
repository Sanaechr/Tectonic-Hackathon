"""Tunable parameters and static vocabularies (no logic)."""

MIN_SCORE = 50            # below: document unusable; best score below: refuse to answer
STRONG_SCORE = 70         # a "solid" document
CONTRADICTION_GAP = 15    # minimal score gap to settle a contradiction by score alone
RECENCY_DAYS = 30         # "noticeably more recent"
TRUSTED_NEWER = 60        # a newer document with at least this score is never silently overruled
MIN_DOC_COVERAGE = 0.12   # share of the question keywords a document must cover (and >= 1 keyword)
SENT_MIN_RATIO = 0.20     # sentence relevance threshold (or >= 2 shared keywords)
FACT_MIN_RATIO = 0.08     # lower threshold for sentences carrying a value or a name
OVERLAP_VALUES = 0.30     # overlap coefficient needed to compare two sentences on values
OVERLAP_NAMES = 0.50      # stricter for name/place conflicts
DEDUP_JACCARD = 0.70      # sentences at least this similar are the same information
CONTRA_JACCARD = 0.25     # topic similarity needed to compare two sentences
NEGATION_JACCARD = 0.30   # similarity needed for negation-only conflicts
MAX_PASSAGES = 12
CORROBORATION_BONUS = 5   # trust bonus per additional document stating the same thing
STALE_DAYS = 365          # a source not modified for longer than this (vs the newest source) is "stale"
STALE_PENALTY = 10        # trust penalty applied to a stale source

STOPWORDS = set("""
a an the of to in on at for from by with and or but if then than that this these those is are was were be been being
can could should would will shall may might do does did it its as into about which what when where who whom how
until before after during through their there here they them he she his her you your we our us i me my not no
all any some more most other such only own same so too very just also each many much whose via per between within whether
""".split())

COUNTRIES = {
    "Belgium": ["belgium", "belgian"],
    "France": ["france", "french"],
    "Germany": ["germany", "german"],
    "Netherlands": ["netherlands", "dutch"],
    "Luxembourg": ["luxembourg"],
}
COUNTRY_WORDS = {w for ws in COUNTRIES.values() for w in ws}
NEGATIONS = {"no", "not", "never", "without", "cannot", "neither", "nor"}
MONTHS = {m: i for i, names in enumerate(
    ["january jan", "february feb", "march mar", "april apr", "may", "june jun", "july jul",
     "august aug", "september sep sept", "october oct", "november nov", "december dec"], 1)
    for m in names.split()}

# Words that turn a number into a *different quantity* ("remaining" vs "total", "planned" vs "actual")
QUALIFIER_WORDS = "remaining total planned estimated original previous initial interim draft"
