"""Freely worded farmer questions for SFT prompts v5 (TRAINING_PLAN.md section 6, "Prompts v5").

v4 asked every question in one template per task, and the deployed model garbled questions worded any other way.
v5 draws each question from these banks. Each entry is (lang, dialect, template); lang is "bn" (Bangla script),
"banglish" (romanised) or "en", and picks how crop, haor and month names and digits are filled in. The first template
of each bank is v4's, so v4-style questions stay covered.

`sft_heldout_wordings.json` holds wordings written separately (by an agent that never saw this file or the repo).
They are used only in the test split, as the `ood_wording` subset, and must never be tuned against.

Slots: negotiation {crop} {offer} [{qty} maunds]; arbitrage one of {qty_kg} {qty_mon} {qty_bosta}, {spot}, optional
{months} {future} {tariff} {handling} and {rot} (a fraction) or {rot_pct}; flood {haor} or {haor_en}, optional
{rain} {sar} {month} (all three or none); storage {topic} or {topic_bn}, optional {crop} or {crop_bn}.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

Wording = tuple[str, str, str]

# Negotiation questions are drawn per dialect group (i % len), so Standard Bangla carries three shares. Chittagonian
# stays v4's single template: the whole group is the out-of-distribution dialect test.
NEGOTIATION_GROUPS: tuple[str, ...] = ("Rangpuri", "Bogura (Varendri)", "Sylheti", "Chittagonian", "Standard Bangla",
                                       "Standard Bangla", "Standard Bangla", "Banglish", "English")
NEGOTIATION_WORDINGS: dict[str, tuple[Wording, ...]] = {
    "Rangpuri": (
        ("bn", "Rangpuri", "বাহে, হামার {qty} মণ {crop} আছে, ফড়িয়া {offer} টাকা কেজি দিবার চায়। বেচমু?"),
        ("bn", "Rangpuri", "ফড়িয়া কয় কেজি {offer} টাকা, হামার {qty} মণ {crop}। দিমু নাকি বাহে?"),
        ("bn", "Rangpuri", "বাহে কন তো, {crop} কেজি {offer} টাকাত বেচা কি ঠিক হইবে?"),
    ),
    "Bogura (Varendri)": (
        ("bn", "Bogura (Varendri)", "হামি {qty} মণ {crop} লিয়া বসি আছি, পাইকার {offer} টাকা কয়। ক্যাংকা করমু?"),
        ("bn", "Bogura (Varendri)", "পাইকার {crop} কেজি {offer} টাকা কচ্চে, হামি কী করমু?"),
        ("bn", "Bogura (Varendri)", "হামার {qty} মণ {crop}, পাইকার {offer} টাকা কেজি দিবি কচ্চে। বেচা ঠিক হবি?"),
    ),
    "Sylheti": (
        ("bn", "Sylheti", "আমার {qty} মণ {crop} আছে, বেপারী {offer} টাকা দিত চায়। কিতা করমু?"),
        ("bn", "Sylheti", "বেপারী কেজিত {offer} টাকা দিবা কইরা কইন, {crop} বেচমু নি?"),
        ("bn", "Sylheti", "ভাই, {qty} মণ {crop} বেচতাম চাই, বেপারী {offer} টাকা কয়। ঠিক আছে নি?"),
    ),
    "Chittagonian": (
        ("bn", "Chittagonian", "আঁর {qty} মণ {crop} আছে, ফড়িয়া {offer} টাকা কয়। কিল্লাই এত কম?"),
    ),
    "Standard Bangla": (
        ("bn", "Standard Bangla", "আমার {qty} মণ {crop} আছে, ফড়িয়া কেজি {offer} টাকা দিতে চাইছে। বিক্রি করব?"),
        ("bn", "Standard Bangla", "ফড়িয়া {crop} কেজি {offer} টাকা বলছে। এই দামে দিলে কি ঠকব?"),
        ("bn", "Standard Bangla", "{qty} মণ {crop} তুলেছি। পাইকার বলছে প্রতি কেজি {offer} টাকা। দামটা কি ঠিক আছে?"),
        ("bn", "Standard Bangla", "ভাই, বেপারী {crop} প্রতি কেজি {offer} টাকা দিতে চায়, বেচব নাকি অপেক্ষা করব?"),
        ("bn", "Standard Bangla", "আজ হাটে আড়তদার {crop} এর দাম কেজি {offer} টাকা ধরেছে। আমার {qty} মণ আছে, দিয়ে দেব?"),
        ("bn", "Standard Bangla", "কেজি {offer} টাকায় {crop} বিক্রি করলে লাভ হবে, নাকি দাম কম?"),
        ("bn", "Standard Bangla", "{crop} {qty} মণ, ফড়িয়া {offer} টাকা কেজি দর দিচ্ছে। ন্যায্য দাম কত হওয়া উচিত?"),
        ("bn", "Standard Bangla", "ঘরে {qty} মণ {crop}, ধার শোধ করতে হবে। ফড়িয়া কেজিপ্রতি {offer} টাকা দেবে বলছে, বেচে দিই?"),
    ),
    "Banglish": (
        ("banglish", "Banglish", "amar {qty} mon {crop} ache, foria kg {offer} taka dite chay. bechbo?"),
        ("banglish", "Banglish", "bhai, paikar {crop} er dam {offer} taka kg bolche, dibo naki?"),
        ("banglish", "Banglish", "{qty} mon {crop} tulsi, bepari per kg {offer} taka offer korse. dam ta ki thik ache?"),
        ("banglish", "Banglish", "foria {offer} tk kg te {crop} nite chay, eta ki fair price?"),
        ("banglish", "Banglish", "ajke haat e {crop} {offer} taka kg, amar {qty} mon ase. ki korbo?"),
    ),
    "English": (
        ("en", "English", "I have {qty} maunds of {crop}. The faria is offering {offer} taka per kg. Should I sell?"),
        ("en", "English", "A trader wants to buy my {crop} at {offer} taka a kilo. Is that a fair price?"),
        ("en", "English", "The paikar offered {offer} tk/kg for {crop}. Sell now or wait?"),
        ("en", "English", "Is {offer} taka per kg a good price for {crop}? I have about {qty} maunds."),
        ("en", "English", "Middleman says {offer} taka per kg for my {qty} maund {crop}, should I take it?"),
    ),
}

ARBITRAGE_WORDINGS: tuple[Wording, ...] = (
    ("bn", "Standard Bangla", "{qty_kg} কেজি আলু আছে। আজ দাম {spot} টাকা, {months} মাস পর {future} টাকা আশা করছি। হিমাগার ভাড়া "
                              "{tariff} টাকা, হ্যান্ডলিং {handling} টাকা, পচনের হার {rot}। রাখব না বেচব?"),
    ("bn", "Standard Bangla", "{qty_kg} কেজি আলু আছে। আজ দাম {spot} টাকা, রাখব না বেচব?"),
    ("bn", "Standard Bangla", "আমার {qty_mon} মণ আলু। এখন বাজারে {spot} টাকা কেজি। হিমাগারে রাখব না বেচে দেব?"),
    ("bn", "Standard Bangla", "{qty_bosta} বস্তা আলু আছে, আজকের দর {spot} টাকা। {months} মাস রাখলে {future} টাকা পাব মনে হয়। কোনটা লাভ?"),
    ("bn", "Standard Bangla", "আলু {qty_mon} মণ। আজ দাম কেজি {spot} টাকা। হিমাগার ভাড়া কেজিতে {tariff} টাকা। এখন বেচব নাকি স্টোরে রাখব?"),
    ("bn", "Standard Bangla", "হিমাগারে রাখার কথা ভাবছি। {qty_kg} কেজি আলু, আজ দাম {spot} টাকা, {months} মাস পর দাম {future} টাকা হতে "
                              "পারে। পচন ধরলে {rot_pct}% নষ্ট হবে। কী করব?"),
    ("bn", "Standard Bangla", "আজকের দাম {spot} টাকা কেজি, আমার {qty_bosta} বস্তা আলু। কোল্ড স্টোরেজে রাখলে লাভ হবে?"),
    ("bn", "Standard Bangla", "{qty_mon} মণ আলু, আজ দাম {spot} টাকা। ভাড়া {tariff} টাকা, লোড-আনলোড {handling} টাকা কেজি। {months} মাস "
                              "পর {future} টাকা হলে রাখা ঠিক হবে?"),
    ("banglish", "Banglish", "{qty_mon} mon alu ache, aj dam {spot} taka. himagar e rakhbo naki bechbo?"),
    ("banglish", "Banglish", "amar {qty_bosta} bosta alu, ajker dor {spot} taka kg. {months} mash rakhle {future} taka pabo. ki korbo?"),
    ("banglish", "Banglish", "aj dam {spot} taka, {qty_kg} kg alu. cold storage e rakhle labh hobe?"),
    ("en", "English", "I have {qty_kg} kg of potatoes. Today's price is {spot} taka per kg. Should I sell now or keep them in "
                      "cold storage?"),
    ("en", "English", "{qty_mon} maunds of potatoes, price today is {spot} taka. If I store for {months} months I expect "
                      "{future} taka. Store or sell?"),
    ("en", "English", "Price today is {spot} taka per kg for my {qty_kg} kg potatoes. Cold storage rent is {tariff} taka, "
                      "handling {handling} taka, rot loss about {rot_pct}%. Store or sell now?"),
)

FLOOD_WORDINGS: tuple[Wording, ...] = (
    ("bn", "Standard Bangla", "{haor} হাওরে {month} মাসে উজানে ৭২ ঘণ্টায় {rain} মিমি বৃষ্টি, রাডারে পানির সংকেত {sar} ডিবি। ধান "
                              "কাটব কখন?"),
    ("bn", "Standard Bangla", "{haor} হাওরে পানি বাড়ছে, বাঁধ ভাঙবে নাকি? ধান কাটব কখন?"),
    ("bn", "Sylheti", "আমরার {haor} হাওরর বান্ধ লইয়া চিন্তাত আছি। অখন কিতা ধান কাটি লাইমু?"),
    ("bn", "Standard Bangla", "{month} মাস চলছে, {haor} হাওরে উজানে তিন দিনে {rain} মিমি বৃষ্টি হয়েছে, স্যাটেলাইট রাডারে {sar} "
                              "ডিবি দেখাচ্ছে। ধান কি এখনই কাটব?"),
    ("bn", "Standard Bangla", "{haor} এলাকায় ঢলের পানি আসার ভয় আছে। আধা পাকা ধান রেখে দেব নাকি কেটে ফেলব?"),
    ("bn", "Standard Bangla", "{haor} হাওরে আমার জমির ধান প্রায় পাকা। বন্যার ঝুঁকি কেমন, কবে কাটা শুরু করব?"),
    ("bn", "Standard Bangla", "{month} মাসে {haor} হাওরে ৭২ ঘণ্টায় বৃষ্টি {rain} মিমি, রাডার সংকেত {sar} ডিবি। বাঁধ ভাঙার ঝুঁকি কত?"),
    ("banglish", "Banglish", "{haor_en} haor e pani barche, dhan kobe katbo?"),
    ("banglish", "Banglish", "{haor_en} e badh vangar voy ache, dhan ki ekhon kete felbo?"),
    ("banglish", "Banglish", "{month} mase {haor_en} haor e 72 ghontay {rain} mm brishti, radar signal {sar} dB. dhan katbo kokhon?"),
    ("en", "English", "Will the embankment at {haor_en} haor break? When should I harvest my Boro rice?"),
    ("en", "English", "In {month}, {haor_en} haor got {rain} mm of upstream rain in 72 hours and the radar shows {sar} dB. "
                      "Should I harvest now?"),
    ("en", "English", "Flash flood risk in {haor_en}? My paddy is almost ripe."),
)

STORAGE_WORDINGS: tuple[Wording, ...] = (
    ("bn", "Standard Bangla", "{topic} নিয়ে বারি/বাউর পরামর্শ কী?"),
    ("bn", "Standard Bangla", "{crop} এর ক্ষেত্রে {topic} কীভাবে করব?"),
    ("bn", "Standard Bangla", "{topic} সম্পর্কে নিয়মটা বলুন।"),
    ("bn", "Standard Bangla", "হিমাগারে রাখার আগে {topic} কেন জরুরি?"),
    ("bn", "Standard Bangla", "{topic} ঠিক না হলে কী ক্ষতি হয়?"),
    ("bn", "Standard Bangla", "{topic_bn} নিয়ে একটু বুঝিয়ে বলবেন?"),
    ("bn", "Standard Bangla", "{crop_bn} চাষিদের জন্য {topic_bn} বিষয়ে পরামর্শ চাই।"),
    ("bn", "Standard Bangla", "ভাই, {topic_bn} ব্যাপারটা কী? আমাদের কী করা দরকার?"),
    ("bn", "Standard Bangla", "{topic_bn} নিয়ে সরকারি নিয়ম কী বলে?"),
    ("banglish", "Banglish", "{topic} niye kichu poramorsho din."),
    ("banglish", "Banglish", "{crop} er jonno {topic} kivabe korbo?"),
    ("en", "English", "What is the advice on {topic}?"),
    ("en", "English", "Can you explain {topic} for {crop}?"),
    ("en", "English", "Tell me the rule about {topic}."),
)

CROP_NAMES: dict[str, dict[str, str]] = {
    "bn": {"Cardinal Potato": "কার্ডিনাল আলু", "Diamant Potato": "ডায়মন্ড আলু", "Green Chili": "কাঁচা মরিচ", "Brinjal": "বেগুন",
           "Boro Rice": "বোরো ধান"},
    "banglish": {"Cardinal Potato": "cardinal alu", "Diamant Potato": "diamond alu", "Green Chili": "kacha morich",
                 "Brinjal": "begun", "Boro Rice": "boro dhan"},
    "en": {"Cardinal Potato": "Cardinal potatoes", "Diamant Potato": "Diamant potatoes", "Green Chili": "green chillies",
           "Brinjal": "brinjal", "Boro Rice": "Boro rice"},
}
MONTH_NAMES: dict[str, dict[int, str]] = {"bn": {3: "মার্চ", 4: "এপ্রিল", 5: "মে"},
                                          "banglish": {3: "March", 4: "April", 5: "May"},
                                          "en": {3: "March", 4: "April", 5: "May"}}
# Each knowledge document's first topic (the one storage questions ask about), in Bangla.
TOPIC_BN: dict[str, str] = {
    "curing": "কিউরিং", "ventilation": "বাতাস চলাচল", "late blight": "নাবি ধসা (লেট ব্লাইট)", "MAP packaging": "MAP প্যাকেজিং",
    "post-harvest loss": "ফসল তোলার পরের ক্ষতি", "pre-cooling": "আগাম ঠান্ডা করা (প্রি-কুলিং)",
    "storage temperature": "সংরক্ষণের তাপমাত্রা", "harvest timing": "ফসল কাটার সময়", "flash flood": "আগাম বন্যা (পাহাড়ি ঢল)",
    "syndicate": "সিন্ডিকেট", "aggregation centre": "সংগ্রহ কেন্দ্র", "cold storage capacity": "হিমাগারের ধারণক্ষমতা",
    "production cost": "উৎপাদন খরচ", "warehouse receipt": "গুদাম রসিদ", "collateral-free loan": "জামানত ছাড়া ঋণ",
    "banned chemicals": "নিষিদ্ধ রাসায়নিক", "transport corridor": "পরিবহন পথ", "variety": "জাত",
}

# Prompts v6: each storage question asks about its own sentence's subject, so the gold passage is the one that answers it.
# v5 asked every sentence of a document about the document's first topic (BARI-CHILI-01's chilling-injury sentence was
# asked as "pre-cooling"), and the model cited a related document instead (TRAINING_PLAN.md section 6). (English, Bangla)
# per sentence, in the order SemanticChunker.sentences gives for each document; build_sft_dataset(6) asserts the counts.
SENTENCE_TOPICS: dict[str, tuple[tuple[str, str], ...]] = {
    "BARI-POT-STORE-01": (("potato curing before cold storage", "হিমাগারে তোলার আগে আলুর কিউরিং"),
                          ("potato cold-store temperature and humidity", "হিমাগারে আলুর তাপমাত্রা ও আর্দ্রতা"),
                          ("cooling rate after loading a potato chamber", "আলু তোলার পর চেম্বার ঠান্ডা করার হার"),
                          ("humidity limits in a potato store", "আলুর হিমাগারে আর্দ্রতার সীমা"),
                          ("potato keeping time and rot in cold storage", "হিমাগারে আলু কতদিন থাকে ও কতটা পচে")),
    "BARI-POT-STORE-02": (("chamber ventilation and CO2 for potatoes", "আলুর চেম্বারে বাতাস চলাচল ও কার্বন ডাই-অক্সাইড"),
                          ("stacking potato bags in a cold store", "হিমাগারে আলুর বস্তা সাজানো"),
                          ("cold-store power cuts and generators", "হিমাগারে লোডশেডিং ও জেনারেটর")),
    "DAE-BLIGHT-01": (("weather that spreads potato late blight", "আলুর নাবি ধসা ছড়ানোর আবহাওয়া"),
                      ("protectant sprays against late blight", "নাবি ধসা ঠেকাতে প্রতিরোধমূলক স্প্রে"),
                      ("curative sprays after late blight lesions", "নাবি ধসার দাগ দেখা দিলে প্রতিকারমূলক স্প্রে"),
                      ("harvest interval and irrigation in blight weather", "নাবি ধসার আবহাওয়ায় সেচ ও ফসল তোলার বিরতি")),
    "BAU-MAP-01": (("modified atmosphere packaging for vegetables", "সবজির মডিফায়েড অ্যাটমোস্ফিয়ার প্যাকেজিং"),
                   ("farmer income gain from grading and MAP", "গ্রেডিং ও MAP-এ কৃষকের আয় বৃদ্ধি"),
                   ("perforated versus sealed vegetable bags", "সবজির জন্য ছিদ্রযুক্ত বনাম বন্ধ ব্যাগ")),
    "BAU-PHL-02": (("share of fruit and vegetables lost after harvest", "ফসল তোলার পর ফল ও সবজি নষ্টের হার"),
                   ("losses of jackfruit, banana, pineapple and mango", "কাঁঠাল, কলা, আনারস ও আমের ক্ষতি"),
                   ("national value of post-harvest spoilage", "দেশে ফসল নষ্টের বার্ষিক আর্থিক ক্ষতি")),
    "BARI-CHILI-01": (("harvesting, grading and pre-cooling green chili", "কাঁচা মরিচ তোলা, বাছাই ও আগাম ঠান্ডা করা"),
                      ("green chili storage temperature and shelf life", "কাঁচা মরিচ সংরক্ষণের তাপমাত্রা ও স্থায়িত্ব"),
                      ("chilling injury in green chili", "ঠান্ডায় কাঁচা মরিচের ক্ষতি"),
                      ("weather for chili anthracnose", "মরিচের অ্যানথ্রাকনোজ রোগের আবহাওয়া")),
    "BARI-BRINJAL-01": (("brinjal storage temperature and chilling injury", "বেগুন সংরক্ষণের তাপমাত্রা ও ঠান্ডাজনিত ক্ষতি"),
                        ("Phomopsis blight and fruit rot in brinjal", "বেগুনের ফোমোপসিস ব্লাইট ও ফল পচা"),
                        ("spray for brinjal fruit and shoot borer", "বেগুনের ডগা ও ফল ছিদ্রকারী পোকার ওষুধ")),
    "BRRI-BORO-01": (("when to harvest Boro rice in the haor", "হাওরে বোরো ধান কাটার সময়"),
                     ("combine harvester speed", "কম্বাইন হারভেস্টারের কাজের গতি"),
                     ("threshing, drying and storing paddy", "ধান মাড়াই, শুকানো ও সংরক্ষণ")),
    "FFWC-HAOR-01": (("causes of haor flash floods", "হাওরে আগাম বন্যার কারণ"),
                     ("Boro losses in the April flash floods", "এপ্রিলের আগাম বন্যায় বোরো ধানের ক্ষতি"),
                     ("satellite radar for flood damage", "বন্যার ক্ষতি নিরূপণে স্যাটেলাইট রাডার"),
                     ("flood alerts and emergency harvest", "বন্যার আগাম সতর্কতা ও জরুরি ধান কাটা")),
    "CPD-SYND-01": (("the five middleman tiers", "পাঁচ স্তরের মধ্যস্বত্বভোগী"),
                    ("middlemen's share and markups", "মধ্যস্বত্বভোগীদের ভাগ ও দাম বৃদ্ধি"),
                    ("Aratdar commission at terminal markets", "পাইকারি বাজারে আড়তদারের কমিশন"),
                    ("bypassing middlemen through collective selling", "যৌথ বিক্রিতে মধ্যস্বত্বভোগী এড়ানো")),
    "WFP-AGG-01": (("location of WFP aggregation centres", "WFP সংগ্রহ কেন্দ্রের অবস্থান"),
                   ("how WFP centres buy and pay farmers", "WFP কেন্দ্রের ক্রয় ও মূল্য পরিশোধ")),
    "BCSA-QUOTA-01": (("the national cold-storage shortfall", "দেশে হিমাগারের ঘাটতি"),
                      ("who holds cold-storage quota", "হিমাগারের কোটা কার হাতে"),
                      ("Munshiganj cold-storage capacity", "মুন্সিগঞ্জের হিমাগার ধারণক্ষমতা"),
                      ("the cold-storage tariff hike", "হিমাগার ভাড়া বৃদ্ধি")),
    "DAM-POT-PRICE-01": (("potato production cost", "আলু উৎপাদনের খরচ"),
                         ("harvest and off-season potato prices", "মৌসুমে ও অফ-সিজনে আলুর দাম"),
                         ("gains from holding potatoes to the off-season", "অফ-সিজন পর্যন্ত আলু ধরে রাখার লাভ")),
    "BB-WHR-01": (("pledging stored crops against a warehouse receipt", "গুদাম রসিদের বিপরীতে ফসল বন্ধক"),
                  ("loan size on stored crops", "গুদামে রাখা ফসলের বিপরীতে ঋণের পরিমাণ"),
                  ("why warehouse-receipt loans help farmers", "গুদাম রসিদ ঋণে কৃষকের সুবিধা")),
    "AGRI-FIN-01": (("collateral-free farm loans", "জামানত ছাড়া কৃষিঋণ"),
                    ("iFarmer financing and produce buying", "আইফার্মারের অর্থায়ন ও ফসল কেনা"),
                    ("evidence lenders check for farm loans", "কৃষিঋণে ঋণদাতা যে প্রমাণ দেখে")),
    "DAE-SAFE-01": (("formalin and calcium carbide bans", "ফরমালিন ও ক্যালসিয়াম কার্বাইড নিষেধাজ্ঞা"),
                    ("lead chromate adulteration", "লেড ক্রোমেট ভেজাল"),
                    ("deregistered pesticides such as DDT", "ডিডিটির মতো নিষিদ্ধ কীটনাশক"),
                    ("registered pesticide use and pre-harvest intervals", "নিবন্ধিত কীটনাশক ব্যবহার ও ফসল তোলার আগে বিরতি")),
    "DAM-TRANS-01": (("truck hire cost per kilometre", "কিলোমিটারপ্রতি ট্রাক ভাড়া"),
                     ("bridge tolls on the way to Dhaka", "ঢাকার পথে সেতুর টোল"),
                     ("night transport and pooled trucks", "রাতে পরিবহন ও যৌথ ট্রাক")),
    "BARI-POT-VAR-01": (("Cardinal and Diamant potato varieties", "কার্ডিনাল ও ডায়মন্ড আলুর জাত"),
                        ("potato grade sizes", "আলুর গ্রেড ও আকার")),
}
SENTENCE_TOPIC_BN: dict[str, str] = {en: bn for topics in SENTENCE_TOPICS.values() for en, bn in topics}
assert len(SENTENCE_TOPIC_BN) == len({bn for bn in SENTENCE_TOPIC_BN.values()}) == sum(map(len, SENTENCE_TOPICS.values())), \
    "every sentence's subject must be unique in English and in Bangla, or a question could match two passages"

_REQUIRED: dict[str, tuple[tuple[str, ...], ...]] = {   # each inner tuple: exactly one of these slots must appear
    "market_negotiation": (("crop",), ("offer",)),
    "arbitrage_math": (("qty_kg", "qty_mon", "qty_bosta"), ("spot",)),
    "flood_harvest": (("haor", "haor_en"),),
    "storage_qa": (("topic", "topic_bn"),),
}
_ALLOWED: dict[str, set[str]] = {
    "market_negotiation": {"crop", "offer", "qty"},
    "arbitrage_math": {"qty_kg", "qty_mon", "qty_bosta", "spot", "months", "future", "tariff", "handling", "rot", "rot_pct"},
    "flood_harvest": {"haor", "haor_en", "rain", "sar", "month"},
    "storage_qa": {"topic", "topic_bn", "crop", "crop_bn"},
}
_SLOT = re.compile(r"\{(\w+)\}")


def slots(template: str) -> list[str]:
    return _SLOT.findall(template)


def check_wording(category: str, wording: Wording) -> None:
    """Fail loudly on a template the renderer would fill wrongly."""
    lang, _, template = wording
    found = slots(template)
    assert lang in CROP_NAMES, f"unknown lang {lang!r}: {template}"
    assert set(found) <= _ALLOWED[category] and len(found) == len(set(found)), f"bad slots {found}: {template}"
    for group in _REQUIRED[category]:
        assert sum(s in found for s in group) == 1, f"needs exactly one of {group}: {template}"
    if category == "flood_harvest":
        readings = {"rain", "sar", "month"} & set(found)
        assert not readings or len(readings) == 3, f"rain, sar and month go together: {template}"
    assert not re.search(r"\d|[০-৯]", _SLOT.sub("", template).replace("৭২", "").replace("72", "")), \
        f"numbers must come from slots (only the 72 h window is written out): {template}"


@lru_cache(maxsize=1)
def heldout_wordings() -> dict[str, tuple[Wording, ...]]:
    """The test-only wordings, checked like the training ones and never equal to one."""
    raw = json.loads((Path(__file__).with_name("sft_heldout_wordings.json")).read_text(encoding="utf-8"))
    train = {t for bank in NEGOTIATION_WORDINGS.values() for _, _, t in bank} | {
        t for bank in (ARBITRAGE_WORDINGS, FLOOD_WORDINGS, STORAGE_WORDINGS) for _, _, t in bank}
    out: dict[str, tuple[Wording, ...]] = {}
    for category, items in raw.items():
        wordings = tuple((w["lang"], w["dialect"], w["template"]) for w in items)
        for wording in wordings:
            check_wording(category, wording)
            assert wording[2] not in train, f"a held-out wording is also a training wording: {wording[2]}"
            assert wording[1] != "Chittagonian", "Chittagonian is the out-of-distribution dialect test"
        out[category] = wordings
    assert set(out) == set(_REQUIRED), f"held-out wordings must cover every task, got {sorted(out)}"
    return out


for _category, _wording in [("market_negotiation", w) for ws in NEGOTIATION_WORDINGS.values() for w in ws] + [
        ("arbitrage_math", w) for w in ARBITRAGE_WORDINGS] + [("flood_harvest", w) for w in FLOOD_WORDINGS] + [
        ("storage_qa", w) for w in STORAGE_WORDINGS]:
    check_wording(_category, _wording)
