"""
Amazon Dietary Supplements compliance — policy decoded as a workflow.

Source: Amazon Seller Central Dietary Supplements policy
(https://sellercentral.amazon.com/help/hub/reference/G55N3JF2WQS7RVNE)
plus publicly documented 2024–2026 TIC / cGMP updates.

Seller Central requires login, so this module encodes the policy as actionable
stages and checklist items for the Commerce OS UI. Treat as a living draft —
verify against the live Amazon help page before production use.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class ChecklistItem(TypedDict):
    id: str
    title: str
    detail: str
    why: str
    evidence: str


class WorkflowStage(TypedDict):
    id: str
    number: int
    title: str
    summary: str
    amazon_focus: str
    items: List[ChecklistItem]


class DemoProduct(TypedDict):
    id: str
    name: str
    category: str
    asin_hint: str
    risk_band: str
    notes: str


POLICY_META = {
    "title": "Amazon Dietary Supplements",
    "marketplace": "Amazon.com (US)",
    "help_url": "https://sellercentral.amazon.com/help/hub/reference/G55N3JF2WQS7RVNE",
    "version_note": (
        "v1 concept — policy text turned into a step workflow. "
        "Amazon may update requirements; confirm on Seller Central before submission."
    ),
}

# Demo catalog for the first concept (Kaya Pure + placeholders).
DEMO_PRODUCTS: List[DemoProduct] = [
    {
        "id": "kaya-shilajit-gummies",
        "name": "Kaya Pure Himalayan Shilajit 7-in-1 Gummies",
        "category": "Dietary supplement · botanical / daily wellness",
        "asin_hint": "Add ASIN when listed",
        "risk_band": "Standard dietary supplement (all categories need cGMP TIC in 2026)",
        "notes": "Primary Kaya Pure SKU for compliance walkthrough.",
    },
    {
        "id": "placeholder-sports",
        "name": "Example — Sports nutrition powder",
        "category": "Sports nutrition (higher testing band)",
        "asin_hint": "—",
        "risk_band": "High-risk testing band (heavy metals, microbes, adulterants)",
        "notes": "Shows how the workflow branches for high-risk categories.",
    },
]


WORKFLOW_STAGES: List[WorkflowStage] = [
    {
        "id": "eligibility",
        "number": 1,
        "title": "Eligibility & prohibitions",
        "summary": "Confirm the product is allowed on Amazon before investing in labs or listing work.",
        "amazon_focus": "Prohibited / restricted dietary supplements",
        "items": [
            {
                "id": "elig-not-recalled",
                "title": "Not named in an FDA recall or safety alert",
                "detail": "Search FDA recall and safety alert databases for the brand, product name, and ingredients.",
                "why": "Recalled or alert-flagged supplements are prohibited on Amazon.",
                "evidence": "Screenshot or link from FDA.gov showing no active recall/alert.",
            },
            {
                "id": "elig-not-misbranded",
                "title": "Label is not false or misleading",
                "detail": "Identity statement, Supplement Facts, and claims must match the actual formula.",
                "why": "Misbranded supplements are prohibited.",
                "evidence": "Current label PDF + formula sheet side-by-side.",
            },
            {
                "id": "elig-no-controlled",
                "title": "No controlled substances / CBD / unapproved drugs",
                "detail": "Exclude CBD, Schedule I–V substances, DEA List I chemicals, GLP-1 agonists, and unapproved peptides.",
                "why": "Amazon bans these ingredients in dietary supplements.",
                "evidence": "Full ingredient list reviewed by regulatory or QA.",
            },
            {
                "id": "elig-no-patches",
                "title": "Not a skin patch marketed as a supplement / detox",
                "detail": "Transdermal patches sold as dietary supplements or detox products are prohibited.",
                "why": "Explicit Amazon prohibition.",
                "evidence": "Product form confirmation (gummy / capsule / powder / liquid).",
            },
            {
                "id": "elig-ftc-fda-letters",
                "title": "No open FTC flag or FDA warning letter on this SKU",
                "detail": "Check brand history for warning letters tied to this product’s claims or ingredients.",
                "why": "Products flagged by FTC or FDA warning letters can be blocked.",
                "evidence": "Internal compliance memo + FDA warning letter search.",
            },
        ],
    },
    {
        "id": "listing",
        "number": 2,
        "title": "Listing attributes & images",
        "summary": "Make the detail page and images prove what is on the physical label.",
        "amazon_focus": "Listing content and product images",
        "items": [
            {
                "id": "list-title",
                "title": "Item name includes the dietary supplement identity",
                "detail": "Title should clearly name the supplement (not a drug-like invented name).",
                "why": "Amazon requires clear dietary supplement identity in listing attributes.",
                "evidence": "Proposed Amazon title string.",
            },
            {
                "id": "list-attrs",
                "title": "Brand, manufacturer, ingredients, and unit count filled",
                "detail": "Attributes must include brand, manufacturer, full ingredients, and count/size (e.g. 30 gummies).",
                "why": "Required listing attributes for dietary supplements.",
                "evidence": "Attribute spreadsheet or Seller Central draft.",
            },
            {
                "id": "list-images-sfp",
                "title": "Images show full English label + Supplement Facts",
                "detail": "Photos must make product name, quantity, complete Supplement Facts (incl. continued panels), ingredients, use directions, and warnings readable.",
                "why": "Amazon requires the full label to be visible in images.",
                "evidence": "High-res label flat + bottle images of all sides.",
            },
            {
                "id": "list-images-owner",
                "title": "Images show brand owner / manufacturer address block",
                "detail": "Name and address of brand owner, manufacturer, packer, or distributor must be visible.",
                "why": "Required on product images for supplements.",
                "evidence": "Image crop of address panel.",
            },
            {
                "id": "list-no-fda-logo",
                "title": "No FDA logo in images or A+ content",
                "detail": "Remove any FDA logo, seal, or implied endorsement graphics.",
                "why": "Amazon forbids FDA logo on supplement images.",
                "evidence": "Creative QA checklist signed off.",
            },
            {
                "id": "list-new-sealed",
                "title": "“New” offers are sealed original packaging",
                "detail": "Condition New must ship in original manufacturer-sealed packaging.",
                "why": "Offer condition rule for supplements.",
                "evidence": "Packaging SOP / FBA prep notes.",
            },
        ],
    },
    {
        "id": "claims",
        "number": 3,
        "title": "Claims, keywords & Supplement Facts alignment",
        "summary": "Treat the Supplement Facts panel as the single source of truth for copy and claims.",
        "amazon_focus": "Claims restrictions and SFP alignment",
        "items": [
            {
                "id": "claim-no-disease",
                "title": "No disease claims or disease keywords",
                "detail": "Listing, bullets, A+, and backend keywords must not name diseases or promise to treat/cure/prevent them.",
                "why": "Disease claims turn supplements into unapproved drugs under FDA rules and Amazon policy.",
                "evidence": "Keyword export scrubbed + copy review.",
            },
            {
                "id": "claim-no-fda-approved",
                "title": "No “FDA approved” language (unless truly approved)",
                "detail": "Dietary supplements are not FDA-approved as drugs; remove that phrasing.",
                "why": "Explicit Amazon restriction.",
                "evidence": "Updated listing copy.",
            },
            {
                "id": "claim-no-drug-compare",
                "title": "No comparisons to prescription drugs / controlled substances",
                "detail": "Avoid drug-adjacent naming (e.g. GLP-1 style names, Viagra-like marks, “legal steroids”).",
                "why": "Amazon blocks drug-adjacent and steroid-effect marketing.",
                "evidence": "Brand naming and creative review.",
            },
            {
                "id": "claim-sfp-match",
                "title": "Ingredient amounts match Supplement Facts exactly",
                "detail": "No inflated raw-material weights; name the ingredient and portion; listing claims must match the panel.",
                "why": "Amazon enforces exact SFP alignment (reports of automated checks).",
                "evidence": "Side-by-side: Supplement Facts vs bullets / A+.",
            },
            {
                "id": "claim-nongmo-docs",
                "title": "Non-GMO (or similar) claims have certificates",
                "detail": "If you claim Non-GMO, hold Non-GMO Project, PCR lab, or USDA Organic proof.",
                "why": "Amazon requires documentation for Non-GMO claims.",
                "evidence": "Certificate PDF on file (or remove the claim).",
            },
        ],
    },
    {
        "id": "certs",
        "number": 4,
        "title": "cGMP certification & product testing",
        "summary": "Prove manufacturing quality (all supplements) and extra labs for high-risk categories.",
        "amazon_focus": "cGMP + testing requirements",
        "items": [
            {
                "id": "cert-cgmp",
                "title": "Valid third-party cGMP for the manufacturing site",
                "detail": "Facility certificate under 21 CFR 111 or 117 from an accepted program (e.g. NSF/ANSI 455-2, UL GMP, USP, SGS, GFSI-benchmarked schemes). Private/FDA inspections alone are not enough.",
                "why": "2026 Amazon policy requires third-party cGMP for all dietary supplements.",
                "evidence": "Current, non-expired cGMP certificate PDF.",
            },
            {
                "id": "cert-coa",
                "title": "Finished-product COA from ISO/IEC 17025 lab",
                "detail": "Identity, potency/assay where applicable, and quality specs for the lot you sell.",
                "why": "Supports authenticity and label accuracy expectations.",
                "evidence": "COA with lab accreditation referenced.",
            },
            {
                "id": "cert-high-risk",
                "title": "High-risk category labs (if applicable)",
                "detail": "Bodybuilding, joint, sexual enhancement, sports nutrition, weight management: heavy metals, microbes, adulterants (e.g. NSF/ANSI 173), and dietary ingredient tolerances.",
                "why": "Amazon requires extra testing for these categories.",
                "evidence": "Lab report package — or N/A with category justification.",
            },
            {
                "id": "cert-docs-authentic",
                "title": "Documents are original (not AI-generated / altered)",
                "detail": "Submit authentic, unmodified certificates and images of the actual listed product.",
                "why": "Amazon rejects synthetic or altered documentation.",
                "evidence": "Files from certifier / lab portals.",
            },
        ],
    },
    {
        "id": "tic",
        "number": 5,
        "title": "TIC provider & Seller Central submission",
        "summary": "Route everything through Amazon’s approved Testing, Inspection & Certification path.",
        "amazon_focus": "Manage Your Compliance / TIC",
        "items": [
            {
                "id": "tic-pick-provider",
                "title": "Choose an Amazon-approved TIC provider",
                "detail": "Examples publicly listed for US: NSF, SGS, UL, Eurofins, Intertek, Mérieux, Certified Laboratories (confirm current list in Seller Central).",
                "why": "Sellers can no longer upload lab packs directly; TIC submits to Amazon.",
                "evidence": "Engagement letter / portal account with TIC.",
            },
            {
                "id": "tic-initiate",
                "title": "Start request in Manage Your Compliance",
                "detail": "From Seller Central, initiate test / appeal per ASIN after Amazon notifies you (often ~90-day window).",
                "why": "Official path to open the compliance case.",
                "evidence": "Screenshot of open compliance case IDs.",
            },
            {
                "id": "tic-fast-track",
                "title": "Check Fast-Track if already certified",
                "detail": "Programs such as NSF, USP, Informed Choice, Clean Label Project, BSCG, GRMA may qualify for accelerated validation.",
                "why": "Can shorten the path when certifications already exist.",
                "evidence": "Fast-Track eligibility note from TIC / Amazon.",
            },
            {
                "id": "tic-provider-submits",
                "title": "TIC submits results to Amazon (not the brand alone)",
                "detail": "Coordinate sample shipment / document pack so the TIC files on your behalf.",
                "why": "Policy change: brand-direct uploads are rejected.",
                "evidence": "TIC confirmation that package was submitted.",
            },
            {
                "id": "tic-monitor",
                "title": "Monitor case until listing stays active",
                "detail": "Track remediation requests from TIC before Amazon takes suppression action.",
                "why": "Amazon may allow fixes via TIC before enforcement.",
                "evidence": "Case status log (open / remediate / cleared).",
            },
        ],
    },
]


STATUS_CHOICES = {
    "todo": "Not started",
    "doing": "In progress",
    "done": "Done",
    "blocked": "Blocked",
    "na": "N/A",
}


def stages() -> List[WorkflowStage]:
    return WORKFLOW_STAGES


def stage_by_id(stage_id: str) -> Optional[WorkflowStage]:
    for stage in WORKFLOW_STAGES:
        if stage["id"] == stage_id:
            return stage
    return None


def products() -> List[DemoProduct]:
    return DEMO_PRODUCTS


def product_by_id(product_id: str) -> Optional[DemoProduct]:
    for product in DEMO_PRODUCTS:
        if product["id"] == product_id:
            return product
    return None


def product_choices() -> Dict[str, str]:
    return {p["id"]: p["name"] for p in DEMO_PRODUCTS}


def default_checklist_state() -> Dict[str, str]:
    state: Dict[str, str] = {}
    for stage in WORKFLOW_STAGES:
        for item in stage["items"]:
            state[item["id"]] = "todo"
    return state


def progress_summary(checklist: Dict[str, str]) -> Dict[str, Any]:
    counts = {key: 0 for key in STATUS_CHOICES}
    for status in checklist.values():
        if status in counts:
            counts[status] += 1
        else:
            counts["todo"] += 1
    actionable = counts["todo"] + counts["doing"] + counts["done"] + counts["blocked"]
    done = counts["done"]
    pct = int(round(100 * done / actionable)) if actionable else 0
    stage_progress = []
    for stage in WORKFLOW_STAGES:
        ids = [item["id"] for item in stage["items"]]
        total = len(ids)
        finished = sum(1 for item_id in ids if checklist.get(item_id) in {"done", "na"})
        stage_progress.append(
            {
                "id": stage["id"],
                "title": stage["title"],
                "number": stage["number"],
                "done": finished,
                "total": total,
                "complete": finished == total and total > 0,
            }
        )
    return {
        "counts": counts,
        "percent": pct,
        "stages": stage_progress,
    }
