"""Seed knowledge base: agronomic, post-harvest, market and policy passages.

Each ``KnowledgeDoc`` is a KrishiNexus summary of guidance published by BARI, BAU,
BRRI, DAE, BCSA, CPD, WFP and Bangladesh Bank, written for retrieval. Every chunk
is indexed with an Anthropic-style *Contextual Retrieval* header (provenance,
crop and district applicability, topics) prepended to its text.

``GRAPH_RULES`` are the pathology / storage rule nodes that the GraphRAG layer
attaches to crops and cold storages, each citing the passages that support it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.mcp_models import Crop

ALL_POTATO = (Crop.CARDINAL_POTATO.value, Crop.DIAMANT_POTATO.value)
POTATO_DISTRICTS = ("Munshiganj", "Bogura", "Rangpur", "Thakurgaon")
HAOR_DISTRICTS = ("Sunamganj", "Kishoreganj", "Netrokona")


@dataclass(frozen=True, slots=True)
class KnowledgeDoc:
    doc_id: str
    title: str
    source: str
    doc_type: str
    year: int
    crops: tuple[str, ...]
    districts: tuple[str, ...]
    topics: tuple[str, ...]
    text: str

    def contextual_header(self) -> str:
        crops = ", ".join(self.crops) if self.crops else "all crops"
        districts = ", ".join(self.districts) if self.districts else "all of Bangladesh"
        return (
            f"[Context: This passage is from '{self.title}', a {self.doc_type} by {self.source} ({self.year}). "
            f"It applies to {crops} in {districts} and covers {', '.join(self.topics)}.]"
        )


@dataclass(frozen=True, slots=True)
class GraphRule:
    rule_id: str
    name: str
    kind: str  # "storage" | "pathology" | "harvest" | "safety" | "market"
    crops: tuple[str, ...]
    statement: str
    cites: tuple[str, ...] = field(default=())


KNOWLEDGE_DOCS: tuple[KnowledgeDoc, ...] = (
    KnowledgeDoc(
        "BARI-POT-STORE-01", "Potato curing and cold-storage protocol",
        "BARI Tuber Crops Research Centre", "post-harvest technical bulletin", 2023,
        ALL_POTATO, POTATO_DISTRICTS, ("curing", "cold storage temperature", "relative humidity", "rot prevention"),
        "Cure freshly harvested table potatoes for 10-14 days in shade at 15-20 C and 85-95% relative humidity so "
        "skin sets and cuts suberise before loading. Store cured tubers at 48-50 F (9-10 C) with 92-95% relative "
        "humidity; this band limits respiration, sprouting and weight loss while avoiding the low-temperature "
        "sweetening that occurs below 4 C. Pull chambers down by no more than 0.5 C per day after loading. "
        "Humidity above 95% causes condensation on tubers and soft rot; below 90% causes shrinkage. Under these "
        "conditions Cardinal and Diamant table potatoes keep 7-8 months with under 2% rot, whereas chambers that "
        "drift outside the band record 2-9% internal rot.",
    ),
    KnowledgeDoc(
        "BARI-POT-STORE-02", "Cold chamber ventilation, CO2 and stacking practice",
        "BARI Post-Harvest Technology Division", "operations guideline", 2022,
        ALL_POTATO, POTATO_DISTRICTS, ("ventilation", "CO2", "stacking", "power failure"),
        "Ventilate potato chambers for about 30 minutes every 6 hours to keep CO2 below 3,000 ppm; above "
        "5,000 ppm tubers develop black heart. Stack 50 kg jute or net bags on pallets with 15 cm gaps between "
        "rows and walls so cold air circulates. During load-shedding a diesel generator must restart the "
        "compressors within 2 hours: without refrigeration chamber temperature rises roughly 0.5 C per hour in "
        "summer and rot risk climbs sharply once tubers exceed 12 C for more than a day.",
    ),
    KnowledgeDoc(
        "DAE-BLIGHT-01", "Late blight (nabi dhosha) forecasting and spray protocol",
        "Department of Agricultural Extension (DAE) Plant Protection Wing", "crop protection advisory", 2024,
        ALL_POTATO, POTATO_DISTRICTS, ("late blight", "fungicide", "pre-harvest interval", "weather trigger"),
        "Late blight (Phytophthora infestans) spreads when night temperatures stay between 10 and 20 C with "
        "relative humidity above 90% for 11 hours or more, typically during foggy December-January spells. Begin "
        "protectant sprays of mancozeb 80WP at 2 g per litre of water at 7-day intervals once these conditions "
        "appear. After the first lesions, switch to a curative mix such as metalaxyl + mancozeb or cymoxanil + "
        "mancozeb at 2 g/L, alternating products. Observe the 7-day pre-harvest interval and stop irrigation "
        "during blight weather.",
    ),
    KnowledgeDoc(
        "BAU-MAP-01", "Modified atmosphere packaging for fresh vegetables",
        "Bangladesh Agricultural University (BAU) Department of Horticulture", "post-harvest research summary", 2022,
        (Crop.GREEN_CHILI.value, Crop.BRINJAL.value), ("Bogura", "Jessore", "Dhaka Karwan Bazar"),
        ("MAP packaging", "post-harvest loss", "farmer income"),
        "Modified atmosphere packaging (MAP) in perforated low-density polyethylene bags slows respiration and "
        "water loss in green chili, brinjal and leafy vegetables. In BAU trials, sorting and grading combined with "
        "MAP cut transit and market losses enough to raise seasonal farmer income by 32%, about US$947 per "
        "smallholder per season. Pre-cool produce "
        "before bagging and avoid sealed non-perforated bags, which trap condensation and cause rot.",
    ),
    KnowledgeDoc(
        "BAU-PHL-02", "Post-harvest loss along fruit and vegetable value chains",
        "Bangladesh Agricultural University (BAU) Post-Harvest Loss Study", "value-chain loss assessment", 2021,
        (), (), ("post-harvest loss", "trader loss", "spoilage cost"),
        "Losses accumulate at every hand-off: 25-43.5% of fruit and vegetable output is lost between field and "
        "consumer. Jackfruit loses about 38%, banana 37%, pineapple 27% and mango 24%; in the banana chain traders "
        "alone lose 30.8% of the volume they handle to bruising, over-ripening and rough transport. Nationally, "
        "post-harvest spoilage of perishables is valued at about US$2.4 billion a year, concentrated where produce "
        "waits in the open sun at haats and arats without grading or cooling.",
    ),
    KnowledgeDoc(
        "BARI-CHILI-01", "Green chili harvest, grading and cool-chain handling",
        "BARI Spices Research Centre", "post-harvest technical bulletin", 2023,
        (Crop.GREEN_CHILI.value,), ("Bogura", "Jessore", "Kurigram"), ("pre-cooling", "storage temperature", "anthracnose"),
        "Harvest green chili in the cool morning, grade out anthracnose-spotted and damaged fruit, and pre-cool "
        "within 4 hours. Store at 7-10 C and 90-95% relative humidity in perforated bags for a 2-3 week shelf "
        "life; at 30 C ambient chili wilts and rots within 2-3 days. Below 7 C chili suffers chilling injury "
        "(pitting and browning). Anthracnose (Colletotrichum capsici) thrives at 25-30 C in humid weather.",
    ),
    KnowledgeDoc(
        "BARI-BRINJAL-01", "Brinjal post-harvest handling and Phomopsis control",
        "BARI Olericulture Division", "post-harvest technical bulletin", 2022,
        (Crop.BRINJAL.value,), ("Jessore", "Bogura", "Rangpur"), ("storage temperature", "chilling injury", "Phomopsis blight"),
        "Brinjal keeps 1-2 weeks at 10-12 C and 90-95% relative humidity; below 10 C it develops chilling injury "
        "with surface pitting and seed browning. Phomopsis blight and fruit rot (Phomopsis vexans) are favoured by "
        "warm humid weather at 26-30 C; remove infected fruit and use DAE-registered fungicides at label dose. "
        "For fruit and shoot borer, emamectin benzoate at label dose with a 3-day pre-harvest interval is preferred "
        "over broad-spectrum organophosphates.",
    ),
    KnowledgeDoc(
        "BRRI-BORO-01", "Boro harvest timing and paddy drying in the haor",
        "Bangladesh Rice Research Institute (BRRI)", "crop management guideline", 2023,
        (Crop.BORO_RICE.value,), HAOR_DISTRICTS, ("harvest timing", "80 percent maturity", "drying", "storage moisture"),
        "In haor areas harvest Boro as soon as 80% of grains are ripe (the 'ashi bhag paklei kata' rule) rather "
        "than waiting for full maturity, because pre-monsoon flash floods can arrive from late March. Combine "
        "harvesters cover about 0.4 ha per hour. Thresh within 24 hours, dry paddy to 12-14% moisture, and store "
        "in hermetic bags on raised platforms; damp paddy above 14% moisture heats and develops storage moulds.",
    ),
    KnowledgeDoc(
        "FFWC-HAOR-01", "Haor flash floods, embankment breaches and early warning",
        "Flood Forecasting and Warning Centre (BWDB) and DAE Sunamganj", "disaster risk briefing", 2022,
        (Crop.BORO_RICE.value,), HAOR_DISTRICTS, ("flash flood", "embankment breach", "Sentinel-1 SAR", "early harvest"),
        "Pre-monsoon flash floods in the north-eastern haor are driven by extreme rainfall over the Meghalaya "
        "hills (Cherrapunji) and the Barak basin; more than about 180 mm in 72 hours upstream can overtop or breach "
        "submersible embankments within one to two days. In April 2017 flash floods destroyed about 65% of the Boro "
        "crop in Sunamganj, 44% in Kishoreganj and 21% in Netrokona. Sentinel-1 radar sees through monsoon cloud "
        "where optical Landsat imagery fails, and detects about twice the crop damage recorded by manual surveys: "
        "VV backscatter below about -18 dB indicates open water. Alerts 72 hours ahead allow emergency harvest of "
        "mature plots.",
    ),
    KnowledgeDoc(
        "CPD-SYND-01", "Intermediary syndicates and price spreads in perishable markets",
        "Centre for Policy Dialogue (CPD), July 2026 study as cited in the KrishiNexus brief", "policy research study", 2026,
        (Crop.GREEN_CHILI.value, Crop.BRINJAL.value) + ALL_POTATO, POTATO_DISTRICTS + ("Dhaka Karwan Bazar", "Jessore"),
        ("syndicate", "value chain", "markup", "Aratdar commission"),
        "Produce passes through five intermediary tiers: Faria, Bepari, Aratdar, Paiker and Retailer. Together they "
        "capture 50-55% of the consumer price, and producer-to-retail markups reach 116% for green chili and over "
        "100% for potato in lean months, which matters because food carries 59% of the consumer price index basket. Aratdars at terminal markets such as Karwan Bazar extract 62.35% of the "
        "Bepari's marketing cost through commission, khajna and arat charges while spending Tk 0 on grading, and "
        "they control auction information. "
        "Collective selling by farmer groups with pooled transport directly to arats or institutional buyers "
        "bypasses the Faria and Bepari tiers.",
    ),
    KnowledgeDoc(
        "WFP-AGG-01", "WFP farmer aggregation centres and fresh food procurement",
        "World Food Programme Bangladesh", "programme description", 2023,
        (Crop.GREEN_CHILI.value, Crop.BRINJAL.value) + ALL_POTATO, ("Cox's Bazar", "Kurigram"),
        ("aggregation centre", "fair price procurement", "grading", "institutional buyer"),
        "WFP links smallholders to 66 farmer aggregation centres, 62 in Cox's Bazar and 4 in Kurigram, that supply fresh "
        "food outlets for Rohingya refugee camps and social-safety-net programmes. Centres buy Grade A and B "
        "vegetables and potatoes at transparent contract prices close to local wholesale, weigh produce on "
        "certified scales and pay through mobile financial services, but each centre accepts limited volumes per "
        "delivery.",
    ),
    KnowledgeDoc(
        "BCSA-QUOTA-01", "Cold-storage capacity, quota capture and tariffs",
        "Bangladesh Cold Storage Association (BCSA) / Department of Agricultural Marketing", "sector statistics brief", 2025,
        ALL_POTATO, POTATO_DISTRICTS, ("cold storage capacity", "quota", "tariff", "smallholder access"),
        "About 12-13 million tonnes of potatoes compete for 2.7-3.27 million tonnes of space in 300-393 cold "
        "storages, a shortfall that costs about US$430 million a year. Traders hold about 45% of storage quota and "
        "plant owners 32.32%, so 77.32% of capacity is captured by non-farmers and smallholders get only 22.68%. "
        "Munshiganj has about 540,760 t of capacity for 1,000,738 t of production. BCSA doubled the tariff (a 100% "
        "hike) from Tk 4-5.50 to Tk 8.00-9.50 per kg per season, and all-in storage costs reach Tk 19-20 per kg in "
        "Thakurgaon, which pushes farmers without storage into distress sales at harvest.",
    ),
    KnowledgeDoc(
        "DAM-POT-PRICE-01", "Potato production cost and seasonal price behaviour",
        "Department of Agricultural Marketing (DAM)", "market price analysis", 2025,
        ALL_POTATO, POTATO_DISTRICTS, ("production cost", "harvest distress price", "seasonal appreciation"),
        "Producing Cardinal or Diamant potatoes costs Tk 15-20 per kg. At peak harvest in February-March "
        "farm-gate prices fall to Tk 5-14 per kg, below cost, while potatoes released from cold storage in "
        "August-September retail at Tk 80-90 per kg in Dhaka. Farmers who can store and hold until the "
        "off-season capture most of this appreciation; those who cannot sell at a loss to Farias.",
    ),
    KnowledgeDoc(
        "BB-WHR-01", "Warehouse-receipt financing for stored crops",
        "Bangladesh Bank Agricultural Credit Department", "credit policy circular summary", 2024,
        ALL_POTATO + (Crop.BORO_RICE.value,), (), ("warehouse receipt", "working capital", "micro-credit"),
        "Crops deposited in licensed storage can be pledged against a warehouse receipt. Banks and MFIs lend up "
        "to about 70% of the stored crop's assessed value as working capital at the agricultural credit rate "
        "(about 9% a year), repaid when the crop is released and sold. This lets farmers avoid distress sales at "
        "harvest while meeting household and next-season input costs.",
    ),
    KnowledgeDoc(
        "AGRI-FIN-01", "Collateral-free agri-credit and digital sourcing partners",
        "United Commercial Bank (UCB) and iFarmer partner terms as cited in the KrishiNexus brief", "partner programme summary", 2026,
        (), (), ("collateral-free loan", "agri-credit interest rate", "digital sourcing", "credit scoring"),
        "UCB extends collateral-free agricultural loans to smallholders at 6% interest, so a farmer with no land "
        "title to mortgage can still finance seed, fertiliser and harvest labour. iFarmer, a Bangladeshi agri-tech "
        "platform, finances farmers and buys their produce for institutional buyers. Both underwrite on evidence: "
        "a signed grading certificate, a pooled B2B truck contract, a cold-storage warehouse receipt and the "
        "farmer's flood exposure.",
    ),
    KnowledgeDoc(
        "DAE-SAFE-01", "Banned chemicals, adulterants and pre-harvest intervals",
        "DAE Plant Protection Wing / Bangladesh Food Safety Authority", "food safety regulation summary", 2024,
        (), (), ("banned chemicals", "formalin", "calcium carbide", "pre-harvest interval"),
        "Formalin is banned as a food preservative under the Formalin Control Act 2015, and calcium carbide is "
        "banned for ripening fruit. Lead chromate used to colour turmeric and lentils is a toxic adulterant. "
        "Persistent organic pollutants such as DDT, endosulfan and heptachlor are deregistered. Use only "
        "DAE-registered pesticides at label dose and respect each product's pre-harvest interval before harvest.",
    ),
    KnowledgeDoc(
        "DAM-TRANS-01", "Truck freight corridors to Dhaka terminal markets",
        "Department of Agricultural Marketing / Roads and Highways Department", "logistics brief", 2025,
        (), ("Bogura", "Rangpur", "Munshiganj", "Thakurgaon", "Jessore", "Dhaka Karwan Bazar"),
        ("transport corridor", "truck freight", "bridge toll", "night transport"),
        "A 5-ton truck costs about Tk 65-70 per km including driver and fuel. Produce from Bogura, Rangpur and "
        "Thakurgaon reaches Dhaka over the Bangabandhu (Jamuna) Bridge (toll about Tk 1,800 for a medium truck); "
        "Jessore produce crosses the Padma Bridge (about Tk 2,800); Munshiganj is linked to Dhaka by the "
        "Dhaka-Mawa expressway. Perishables should move at night to avoid heat, and pooling smallholder lots to "
        "fill a truck cuts freight to Tk 2-4 per kg.",
    ),
    KnowledgeDoc(
        "BARI-POT-VAR-01", "Cardinal and Diamant potato varieties for storage and export",
        "BARI Tuber Crops Research Centre", "variety profile", 2022,
        ALL_POTATO, ("Rangpur", "Thakurgaon", "Bogura", "Munshiganj"), ("variety", "dormancy", "export grade"),
        "Cardinal is a red-skinned, high-yielding table variety widely grown in Munshiganj and the northern "
        "districts; Diamant is a yellow-skinned variety favoured for export and processing with slightly longer "
        "storability. Both need full skin set and curing before cold storage and are graded A (55 mm and above, "
        "no defects), B (35-55 mm) and C (undersized or damaged); only Grade A and B lots should go into long-term storage.",
    ),
)

GRAPH_RULES: tuple[GraphRule, ...] = (
    GraphRule("RULE-POT-STORE", "Store potatoes at 48-50 F / 92-95% RH after curing", "storage", ALL_POTATO,
              "Cure 10-14 days, then hold 9-10 C and 92-95% RH; ventilate to keep CO2 under 3,000 ppm.",
              ("BARI-POT-STORE-01", "BARI-POT-STORE-02")),
    GraphRule("RULE-POT-BLIGHT", "Late blight spray trigger", "pathology", ALL_POTATO,
              "Night 10-20 C with RH > 90% for 11 h: mancozeb 2 g/L every 7 days; 7-day PHI.", ("DAE-BLIGHT-01",)),
    GraphRule("RULE-CHILI-COOL", "Pre-cool chili to 7-10 C within 4 h", "storage", (Crop.GREEN_CHILI.value,),
              "7-10 C, 90-95% RH, perforated bags; chilling injury below 7 C.", ("BARI-CHILI-01", "BAU-MAP-01")),
    GraphRule("RULE-CHILI-ANTHRACNOSE", "Anthracnose watch at 25-30 C humid weather", "pathology", (Crop.GREEN_CHILI.value,),
              "Grade out spotted fruit; registered fungicide at label dose.", ("BARI-CHILI-01",)),
    GraphRule("RULE-BRINJAL-CHILL", "Hold brinjal at 10-12 C, never below 10 C", "storage", (Crop.BRINJAL.value,),
              "10-12 C and 90-95% RH for 1-2 weeks.", ("BARI-BRINJAL-01", "BAU-MAP-01")),
    GraphRule("RULE-BORO-80PCT", "Harvest haor Boro at 80% maturity", "harvest", (Crop.BORO_RICE.value,),
              "Harvest at 80% ripeness; dry to 12-14% moisture within 24 h.", ("BRRI-BORO-01", "FFWC-HAOR-01")),
    GraphRule("RULE-SAFETY-BANNED", "No formalin, carbide or deregistered pesticides", "safety", (),
              "Formalin, calcium carbide, lead chromate and POP pesticides are prohibited.", ("DAE-SAFE-01",)),
    GraphRule("RULE-MARKET-FLOOR", "Do not sell below production cost when storage pays", "market", ALL_POTATO,
              "Below Tk 15/kg with open quota and dPi > 0: store and borrow against the warehouse receipt.",
              ("DAM-POT-PRICE-01", "BCSA-QUOTA-01", "BB-WHR-01")),
)
