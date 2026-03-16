ALLOWED_BLOCK_TYPES: set[str] = {
    # ===== Standard Block Typen (# - ######) =====
    "title",    # Block nach Titel (#)
    "heading",  # Block nach Überschrift (## - #####)
    "text",     # Base Block Typ
    "special",  # Sammlung von allen 'undefined' Block Typen

    # ===== Spezielle Block Typen (######) =====
    # Standard Paper Abschnitte
    "definition",
    "theorem",
    "lemma",
    "corollary",
    "proposition",
    "proof",
    "remark",
    "claim",
    "observation",
    "example",
    "algorithm",
    "axiom",
    "assumption",
    "conjecture",
    "question",
    "counterexample",
    "statement",
    "problem",
    "note",
    "notation",
    "convention",
    "result",
    "case",
    "figure",
    "table",

    # Tendenziell irrelevante Paper Abschnitte
    "abstract",
    "keywords",
    "pacs",
    "msc",
    "doi",
    "contents",
    "index",
    "acknowledgments",

    # Misc
    "outline",
    "addendum",
    "prerequisites",
    "disclaimer",
    "conclusion",
    "discussion",
}

# Datensatz-spezifische, spezielle Block Typen, die eine andere Schreibweise, Abkürzung,
# Übersetzung, o.ä. von den Block Typen aus ALLOWED_BLOCK_TYPES darstellen.
# Format ist [alias, korrekter Block Typ].
BLOCK_TYPES_ALIASES: dict[str, str] = {
    # keywords
    "key": "keywords",
    "keyword": "keywords",

    # Mehrzahl
    "remarks": "remark",
    "examples": "example",
    "assumptions": "assumption",
    "hypothesis": "assumption",
    "hypotheses": "assumption",

    # acknowledgments
    "acknowledgement": "acknowledgments",
    "acknowledgements": "acknowledgments",
    "acknowledgment": "acknowledgments",
    "acknowledgments": "acknowledgments",
    "acknowledgments\u200b": "acknowledgments",

    # abstract / contents
    "?abstractname?": "abstract",
    "abstractname": "abstract",
    "?contentsname?": "contents",
    "contentsname": "contents",

    # sub-*
    "sublemma": "lemma",
    "subfact": "statement",
    "fact": "statement",
    "facts": "statement",

    # proposition
    "prop": "proposition",

    # corollary
    "corolary": "corollary",
    "corrolary": "corollary",
    "corallary": "corollary",
    "corolary.": "corollary",
    "corrolary.": "corollary",

    # theorem / definition
    "theorem-definition": "theorem",
    "theorem–definition": "theorem",
    "definition-lemma": "definition",
    "theoreme": "theorem",
    "theorem(kamienny": "theorem",

    # Fremdsprachen: französisch / spanisch / portugisisch / italienisch / japanisch
    "définition": "definition",
    "théorème": "theorem",
    "theorème": "theorem",
    "lemme": "lemma",
    "corollaire": "corollary",
    "remarque": "remark",
    "preuve": "proof",
    "exemple": "example",
    "problème": "problem",
    "remerciements": "acknowledgments",
    "definición": "definition",
    "definição": "definition",
    "definizione": "definition",
    "proposición": "proposition",
    "proposizione": "proposition",
    "proposição": "proposition",
    "lema": "lemma",
    "corolario": "corollary",
    "corolário": "corollary",
    "observación": "observation",
    "observação": "observation",
    "osservazione": "observation",
    "ejemplo": "example",
    "exemplo": "example",
    "teorema": "theorem",
    "概要": "abstract",
    "証明": "proof",
}
