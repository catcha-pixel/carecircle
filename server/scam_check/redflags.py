"""Rule-based red flags for scam messages, with plain-language explanations.

Each flag has:
  - strength: "strong" (almost never in legit messages), "medium", or "weak"
  - patterns: regexes (English + Spanish), matched case-insensitively
  - why: a short explanation a non-technical reader can understand, in en/es
"""

import re
from dataclasses import dataclass, field


@dataclass
class Flag:
    id: str
    strength: str
    patterns: list
    why: dict
    compiled: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        self.compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def match(self, text):
        for rx in self.compiled:
            m = rx.search(text)
            if m:
                return m.group(0)
        return None


FLAGS = [
    Flag(
        "gift_cards", "strong",
        [r"gift ?cards?", r"google play card", r"itunes card", r"tarjetas? de regalo"],
        {
            "en": "It asks for gift cards. Real companies and government offices never ask you to pay with gift cards.",
            "es": "Pide tarjetas de regalo. Las empresas y el gobierno nunca piden pagos con tarjetas de regalo.",
        },
    ),
    Flag(
        "sensitive_info", "strong",
        [r"social security number", r"\bssn\b", r"\bpin\b", r"password", r"card number",
         r"medicare number", r"date of birth", r"reply with (the|your) .{0,20}code",
         r"(username|user name) and password", r"n[uú]mero de seguro social", r"contrase[nñ]a"],
        {
            "en": "It asks for private information like your Social Security number, PIN, password, or a code. Never share these by text.",
            "es": "Pide informacion privada como su numero de Seguro Social, PIN, contrasena o un codigo. Nunca los comparta por mensaje.",
        },
    ),
    Flag(
        "pay_to_receive", "strong",
        [r"(pay|send)( the| a)? \$?[\d.,]+ .{0,40}(to receive|to release|to claim|processing fee|shipping)",
         r"(processing|release|clearance|shipping) fee", r"first .{0,30}send \$?\d+"],
        {
            "en": "It says you must pay a fee to receive money or a prize. If you really won something, you would not have to pay for it.",
            "es": "Dice que debe pagar para recibir dinero o un premio. Si de verdad gano algo, no tendria que pagar.",
        },
    ),
    Flag(
        "family_emergency_secret", "strong",
        [r"don'?t tell (mom|dad|anyone|my parents)", r"please don'?t tell", r"no le digas",
         r"(new|my new) (phone )?number.{0,80}(urgent|money|bill|help|accident|hospital)",
         r"(arrested|in jail|bail|car accident|in the hospital).{0,80}(money|send|wire|pay|\$)",
         r"(accidente|policia|carcel).{0,80}(dinero|mandes)"],
        {
            "en": "It sounds like a family member in an emergency asking for money and secrecy. Scammers pretend to be grandchildren. Call your family member at their usual number to check.",
            "es": "Parece un familiar en una emergencia pidiendo dinero y secreto. Los estafadores se hacen pasar por nietos. Llame a su familiar a su numero de siempre.",
        },
    ),
    Flag(
        "threat", "medium",
        [r"arrest", r"warrant", r"legal (case|action)", r"suspended", r"\blocked\b", r"\blimited\b",
         r"shut off", r"disconnect", r"lose (your )?(coverage|benefits)", r"will (stop|be closed)",
         r"bloquead[ao]", r"suspensi[oó]n"],
        {
            "en": "It threatens you (arrest, a locked account, or service shut off) to scare you into acting fast.",
            "es": "Lo amenaza (arresto, cuenta bloqueada o corte de servicio) para asustarlo y que actue rapido.",
        },
    ),
    Flag(
        "urgency", "medium",
        [r"immediately", r"right away", r"\bnow\b", r"today only", r"within \d+ (hours|minutes)",
         r"in \d+ minutes", r"final (notice|disconnection)", r"\bact now\b", r"before it expires",
         r"limited spots", r"\burgent", r"hurry", r"inmediatamente", r"urgente",
         r"pr[oó]ximas \d+ horas"],
        {
            "en": "It rushes you. Scammers create a deadline so you don't have time to think or ask someone.",
            "es": "Lo apresura. Los estafadores ponen una fecha limite para que no tenga tiempo de pensar o preguntar.",
        },
    ),
    Flag(
        "hard_to_reverse_payment", "medium",
        [r"\bzelle\b.{0,60}(send|pay|payment)", r"(send|pay).{0,40}\bzelle\b", r"\bwire(d)?\b",
         r"bitcoin", r"\bcrypto", r"cash ?app", r"western union", r"moneygram"],
        {
            "en": "It wants a payment method that is hard to get back once sent (wire, Zelle, crypto, Cash App).",
            "es": "Quiere un pago dificil de recuperar (transferencia, Zelle, cripto, Cash App).",
        },
    ),
    Flag(
        "prize", "medium",
        [r"congratulations", r"you('ve| have)? (won|been selected)", r"\bwinner\b",
         r"claim (your|the) (prize|reward|funds|refund)", r"\bfree\b.{0,40}(card|gift|prize|brace|testing)",
         r"sweepstakes", r"pre-?approved"],
        {
            "en": "It offers a prize, reward, or money you didn't ask for. If it sounds too good to be true, it usually is.",
            "es": "Ofrece un premio o dinero que usted no pidio. Si suena demasiado bueno para ser verdad, probablemente no lo es.",
        },
    ),
    Flag(
        "callback_number", "medium",
        [r"call (now|today|immediately|us|our|amazon|support|the)?.{0,30}\b1?-?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}",
         r"press 1"],
        {
            "en": "It gives you a phone number to call. Scammers answer those numbers. Instead, call the number on your card, bill, or the company's real website.",
            "es": "Le da un numero para llamar. Los estafadores contestan esos numeros. Mejor llame al numero de su tarjeta, factura o sitio oficial.",
        },
    ),
    Flag(
        "government_impersonation", "medium",
        [r"\birs\b", r"social security (administration|office)", r"\bssa\b", r"sheriff", r"jury duty",
         r"\bdmv\b", r"\bmedicare\b.{0,60}(call|send|eligible|qualify|lose)"],
        {
            "en": "It claims to be from the government. Agencies like the IRS, Social Security, and Medicare contact you by mail first and never threaten you by text.",
            "es": "Dice ser del gobierno. El IRS, el Seguro Social y Medicare le escriben por correo primero y nunca lo amenazan por mensaje.",
        },
    ),
    Flag(
        "move_to_other_app", "medium",
        [r"whatsapp", r"telegram", r"signal app"],
        {
            "en": "It asks you to move the conversation to another app, which scammers do to avoid being caught.",
            "es": "Le pide pasar la conversacion a otra aplicacion, algo que hacen los estafadores para no ser detectados.",
        },
    ),
    Flag(
        "stranger_opener", "weak",
        [r"wrong number", r"is this \w+\?", r"got your number from", r"sorry to bother you",
         r"you seem nice"],
        {
            "en": "It's a friendly message from a stranger. This is a common way romance and investment scams begin.",
            "es": "Es un mensaje amistoso de un desconocido. Asi empiezan muchas estafas romanticas o de inversion.",
        },
    ),
    Flag(
        "easy_money", "medium",
        [r"earn \$?\d+", r"earn money", r"get paid \$?\d+", r"make \$\d+",
         r"\$\d+.{0,10}(per|a) (day|week|hour)", r"work from home", r"money at home",
         r"remote position", r"trading crypto", r"mentor"],
        {
            "en": "It promises easy money or a job you didn't apply for. These are often scams that end up costing you money.",
            "es": "Promete dinero facil o un trabajo que no solicito. Suelen ser estafas que le terminan costando dinero.",
        },
    ),
]

# Signs that a message follows good security practice (seen in real bank/pharmacy texts).
SAFE_SIGNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(never|don'?t|do not) (ask|share|call you)",
        r"number on the back of your card",
        r"contact your bank directly",
        r"if this was you, no action is needed",
        r"reply stop to opt out",
        # Real companies send you to the account you already have, not to a new link.
        r"(sign in to|log in to|available in|view it in) (your )?(online |member )?(account|portal|app|banking)",
    ]
]

# Flags that always deserve at least a "be careful", whatever the model says.
MIN_CAREFUL = {"stranger_opener", "move_to_other_app"}

# Official domains we trust. A link to anything else that uses a brand name is a warning.
OFFICIAL_DOMAINS = {
    "chase.com", "wellsfargo.com", "bankofamerica.com", "citi.com", "usps.com", "ups.com",
    "fedex.com", "amazon.com", "apple.com", "paypal.com", "venmo.com", "netflix.com",
    "costco.com", "walmart.com", "target.com", "ssa.gov", "irs.gov", "medicare.gov", "ca.gov",
    "dmv.ca.gov", "sce.com", "socalgas.com", "pge.com", "kp.org", "cvs.com", "walgreens.com",
    "bankofthewest.com", "thefastrak.com", "e-zpassny.com",
}
BRAND_WORDS = [
    "chase", "wellsfargo", "wf", "bankofamerica", "boa", "citi", "usps", "ups", "fedex", "amazon",
    "apple", "paypal", "venmo", "netflix", "costco", "walmart", "target", "ssa", "irs", "medicare",
    "dmv", "edison", "pge", "fastrak", "ezpass", "toll", "customs", "zelle", "cashapp", "geek",
]
RISKY_TLDS = {"top", "xyz", "info", "co", "click", "live", "icu", "online", "site", "shop", "buzz", "net"}

DOMAIN_RX = re.compile(r"\b((?:[a-z0-9-]+\.)+([a-z]{2,}))(?:/\S*)?\b", re.IGNORECASE)

LINK_WHY = {
    "en": "It has a link that pretends to be a real company but isn't their real website ({domain}). Don't tap it.",
    "es": "Tiene un enlace que finge ser de una empresa real pero no es su sitio oficial ({domain}). No lo toque.",
}


def check_links(text):
    """Return suspicious domains found in the text."""
    bad = []
    for m in DOMAIN_RX.finditer(text):
        domain = m.group(1).lower().rstrip(".")
        tld = m.group(2).lower()
        if domain in OFFICIAL_DOMAINS or any(domain.endswith("." + d) for d in OFFICIAL_DOMAINS):
            continue
        squashed = domain.replace("-", "").replace(".", "")
        uses_brand = any(b in squashed for b in BRAND_WORDS)
        if uses_brand or tld in RISKY_TLDS or "-" in domain:
            bad.append(domain)
    return bad


def find_flags(text, lang="en"):
    """Return list of dicts: {id, strength, evidence, why} for each red flag found."""
    found = []
    for f in FLAGS:
        ev = f.match(text)
        if ev:
            found.append({"id": f.id, "strength": f.strength, "evidence": ev, "why": f.why[lang]})
    for domain in check_links(text):
        found.append({
            "id": "fake_link", "strength": "strong", "evidence": domain,
            "why": LINK_WHY[lang].format(domain=domain),
        })
    return found


def safe_signs(text):
    return [rx.search(text).group(0) for rx in SAFE_SIGNS if rx.search(text)]
