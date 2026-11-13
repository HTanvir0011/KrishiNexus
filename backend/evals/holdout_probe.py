"""Blind holdout probe for the retrieval stack: 66 farmer questions the retrieval rules never saw.

The 19-question ``RAG_EVAL_SET`` was written by the same team that wrote the intent rules, so its precision of 1.00
is not evidence of generalisation. These probes were generated on 2026-10-29 by six independent agents that each read
ONLY ``rag/knowledge_seed.py`` (one third of the docs each) and wrote natural farmer questions in six surface forms
(Standard Bangla, Rangpuri, Sylheti, Bogura, Banglish, English), plus negation traps and cross-doc distractors.
Caveat, stated for honesty: the generators worked inside this repository and its contract file mentions the intent
trigger words, so the set is *independent of*, not provably *blind to*, the retrieval rules. Scores from this set are
reported separately from the curated eval set and must never be folded into it.

Run:  cd backend && .venv/Scripts/python -m evals.holdout_probe
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel

from config import now_bdt
from mcp_servers.agri_weather_sar_mcp import NETWORK_BLACKOUT
from rag.knowledge_seed import KNOWLEDGE_DOCS
from schemas.mcp_models import Crop


class HoldoutProbe(BaseModel):
    question: str
    district: str | None
    crop: Crop | None
    gold_doc: str
    dialect: str
    kind: Literal["topical", "paraphrase", "negation", "cross_doc"]


HOLDOUT_PROBES: tuple[HoldoutProbe, ...] = (
    HoldoutProbe(question='আলু তোলার পর হিমাগারে ঢোকানোর আগে কতদিন ছায়ায় রাখা লাগে, আর তখন ঘরের গরম-ঠান্ডা কেমন হওয়া চাই?', district='Munshiganj', crop=Crop('Cardinal Potato'),
                 gold_doc='BARI-POT-STORE-01', dialect='Standard Bangla', kind='topical'),
    HoldoutProbe(question='হিমাগারের চেম্বারে কত ডিগ্রি আর কত ভাগ আর্দ্রতায় রাখলে আলু সাত-আট মাস পর্যন্ত ভালো থাকে?', district='Thakurgaon', crop=Crop('Diamant Potato'),
                 gold_doc='BARI-POT-STORE-01', dialect='Standard Bangla', kind='paraphrase'),
    HoldoutProbe(question='vai amar alu cold storage e 4 degree er niche namay dile naki misti hoye jay? thanda koto rakhle ei somossa hobe na?', district=None, crop=Crop('Cardinal Potato'),
                 gold_doc='BARI-POT-STORE-01', dialect='Banglish', kind='paraphrase'),
    HoldoutProbe(question='হিমাগারের বন্ধ ঘরে কার্বন ডাই-অক্সাইড বেশি জমে গেলে আলুর ভেতরে কী রোগ ধরে, আর কতক্ষণ পরপর বাতাস ঢোকাতে হবে?', district=None, crop=Crop('Cardinal Potato'),
                 gold_doc='BARI-POT-STORE-02', dialect='Standard Bangla', kind='topical'),
    HoldoutProbe(question='কারেন্ট গেলে জেনারেটর কত ঘণ্টার মধ্যে চালু না করলে চেম্বারের আলু পচার ভয় বেড়ে যায়?', district='Rangpur', crop=Crop('Diamant Potato'),
                 gold_doc='BARI-POT-STORE-02', dialect='Standard Bangla', kind='topical'),
    HoldoutProbe(question='হামাকেরে আলুর বস্তাগুলা চেম্বারোত ক্যাংকা কইরা সাজালে ঠান্ডা বাতাসটা সগল জাগাত ঘুরবি?', district='Bogura', crop=Crop('Cardinal Potato'),
                 gold_doc='BARI-POT-STORE-02', dialect='Bogura (Varendri)', kind='paraphrase'),
    HoldoutProbe(question='পৌষ-মাঘের ঘন কুয়াশায় আলুর নাবি ধসা কোন আবহাওয়ায় ছড়ায়, আর প্রথম স্প্রে কখন শুরু করা উচিত?', district='Munshiganj', crop=Crop('Cardinal Potato'),
                 gold_doc='DAE-BLIGHT-01', dialect='Standard Bangla', kind='topical'),
    HoldoutProbe(question='আলুর পাতাত কালা দাগ দেখা দিসে, অখন কুন ওষুধ কতটুক পানিত মিশাইয়া দিতাম?', district=None, crop=Crop('Cardinal Potato'),
                 gold_doc='DAE-BLIGHT-01', dialect='Sylheti', kind='paraphrase'),
    HoldoutProbe(question='ধসার ওষুধ ছিটানোর পর কত দিন অপেক্ষা করে আলু তোলা নিরাপদ, আর ওই সময় সেচ দেওয়া যাবে কি?', district='Thakurgaon', crop=Crop('Diamant Potato'),
                 gold_doc='DAE-BLIGHT-01', dialect='Standard Bangla', kind='paraphrase'),
    HoldoutProbe(question='কোনো ছত্রাকনাশক স্প্রে না করেই শুধু ঠিকঠাক ঠান্ডা ঘরে রেখে আলুর পচন দুই ভাগের নিচে রাখা যায় কি — কোন শর্তে?', district='Munshiganj', crop=Crop('Cardinal Potato'),
                 gold_doc='BARI-POT-STORE-01', dialect='Standard Bangla', kind='negation'),
    HoldoutProbe(question='হিমাগারের ভেতরের মতো ঠান্ডা আর ভেজা হাওয়া যদি রাতে মাঠেই পড়ে, তাহলে দাঁড়ানো আলু গাছের কী বিপদ আর কী করণীয়?', district='Rangpur', crop=Crop('Cardinal Potato'),
                 gold_doc='DAE-BLIGHT-01', dialect='Standard Bangla', kind='cross_doc'),
    HoldoutProbe(question='বাহে, মরিচ আর বেগুন বাজারত নিবার আগোত কোন ধরনের ব্যাগত ভরলে পচন কম হইবে?', district='Bogura', crop=Crop('Green Chili'),
                 gold_doc='BAU-MAP-01', dialect='Rangpuri', kind='topical'),
    HoldoutProbe(question='হামরা যদি সবজিগুলা বাছাই করি, গ্রেড করি আর প্যাকেট করি বেচাই, তাইলে এক মৌসুমোত হামার আয় কতখানি বাড়ির পায়?', district=None, crop=Crop('Brinjal'),
                 gold_doc='BAU-MAP-01', dialect='Rangpuri', kind='paraphrase'),
    HoldoutProbe(question='Ami kacha morich polythene bag e bhore pathate chai — bag ta futo kora lagbe naki ekdom sealed rakhbo? Ar bag e bhorar age kichu korte hobe?', district='Jessore', crop=Crop('Green Chili'),
                 gold_doc='BAU-MAP-01', dialect='Banglish', kind='topical'),
    HoldoutProbe(question='কলা নিয়া যাবার পথোত খালি বেপারীলার হাতোতে কত ভাগ মাল নষ্ট হয়, কন তো বাহে?', district=None, crop=None,
                 gold_doc='BAU-PHL-02', dialect='Rangpuri', kind='topical'),
    HoldoutProbe(question='ক্ষেত থেকে ভোক্তার হাতে পৌঁছাতে আমাদের দেশে ফল ও সবজির মোট কত শতাংশ নষ্ট হয়ে যায়, আর টাকার অঙ্কে সেটা বছরে কত দাঁড়ায়?', district=None, crop=None,
                 gold_doc='BAU-PHL-02', dialect='Standard Bangla', kind='paraphrase'),
    HoldoutProbe(question='কাঁঠাল, কলা, আনারস আর আমের মইধ্যে কোনটা তোলার পর সবচায়া বেশি নষ্ট হয় বাহে?', district=None, crop=None,
                 gold_doc='BAU-PHL-02', dialect='Rangpuri', kind='topical'),
    HoldoutProbe(question='মুই কাঁচা মরিচ দিনের কোন সময়ত তুলিম, আর তুলির পর কতক্ষণের ভিতরোত ঠান্ডা করা নাগবে?', district='Kurigram', crop=Crop('Green Chili'),
                 gold_doc='BARI-CHILI-01', dialect='Rangpuri', kind='topical'),
    HoldoutProbe(question='মরিচ কত ডিগ্রিত থুইলে দুই-তিন সপ্তাহ টিকি থাকে, আর বেশি ঠান্ডাত থুইলে কি হয় বাহে?', district='Bogura', crop=Crop('Green Chili'),
                 gold_doc='BARI-CHILI-01', dialect='Rangpuri', kind='paraphrase'),
    HoldoutProbe(question='My chili fruits are getting dark sunken spots when the weather turns warm and damp. Which disease is this, and what should I sort out before selling?', district='Jessore', crop=Crop('Green Chili'),
                 gold_doc='BARI-CHILI-01', dialect='English', kind='topical'),
    HoldoutProbe(question='কোনো প্যাকেট-ট্যাকেট বা ব্যাগ ছাড়ায়, খালি ঠান্ডা করি মরিচ থুইলে তাপমাত্রা আর ভিজাভাব কতখানি রাখা নাগবে?', district=None, crop=Crop('Green Chili'),
                 gold_doc='BARI-CHILI-01', dialect='Rangpuri', kind='negation'),
    HoldoutProbe(question='বেপারীলার হাতোত এত মাল নষ্ট হয় শুনি — হামরা নিজেরায় বাছাই করি ব্যাগোত ভরি বেচাইলে মৌসুমোত কত টাকা বাড়তি পামো?', district='Bogura', crop=Crop('Green Chili'),
                 gold_doc='BAU-MAP-01', dialect='Rangpuri', kind='cross_doc'),
    HoldoutProbe(question='আমার বেগুন তুলার বাদে কয়দিন ভালা থাকব? কত ঠান্ডাত আর কততা ভেজা বাতাসো রাখলে ফচত না?', district=None, crop=Crop('Brinjal'),
                 gold_doc='BARI-BRINJAL-01', dialect='Sylheti', kind='topical'),
    HoldoutProbe(question='গরম ভেজা দিনো বেগুনর ফলো দাগ ফড়িয়া ফচি যার — ই রোগর নাম কিতা, আর কিতা দিলে থামব?', district=None, crop=Crop('Brinjal'),
                 gold_doc='BARI-BRINJAL-01', dialect='Sylheti', kind='topical'),
    HoldoutProbe(question='Begun er dal ar fol e poka dhukia chidro korer — kun oshudh dile valo, ar spray korar koto din bade begun tula jaibo?', district='Jessore', crop=Crop('Brinjal'),
                 gold_doc='BARI-BRINJAL-01', dialect='Banglish', kind='topical'),
    HoldoutProbe(question='হাওরো আমরার বোরো ধান কততা ফাকলে কাটা ধরতাম? হকল ধান ফাকা অওয়া ফর্যন্ত বইয়া থাকমু নি?', district='Sunamganj', crop=Crop('Boro Rice'),
                 gold_doc='BRRI-BORO-01', dialect='Sylheti', kind='topical'),
    HoldoutProbe(question='ধান মাড়ানির বাদে কততা হুকাইলে গুদামো রাখা যাইব? ভেজা ভেজা থাকলে কিতা অয়?', district='Netrokona', crop=Crop('Boro Rice'),
                 gold_doc='BRRI-BORO-01', dialect='Sylheti', kind='topical'),
    HoldoutProbe(question='হাওরের বোরো কি পুরোপুরি পাকার আগেই কেটে ফেলা উচিত? আশি ভাগ পাকা অবস্থায় কাটলে লোকসান হবে না তো?', district='Kishoreganj', crop=Crop('Boro Rice'),
                 gold_doc='BRRI-BORO-01', dialect='Standard Bangla', kind='paraphrase'),
    HoldoutProbe(question='মেঘালয়র ফাড়ো জোরে বৃষ্টি অইলে আমরার বান্ধ কয়দিনর মাঝে ভাঙতে ফারে? উজানো কততা বৃষ্টি অইলে বিপদ বুঝতাম?', district='Sunamganj', crop=Crop('Boro Rice'),
                 gold_doc='FFWC-HAOR-01', dialect='Sylheti', kind='topical'),
    HoldoutProbe(question='বানর খবর কয় ঘণ্টা আগে ফাইলে আমরা ফাকা খেতর ধান কাটি লাইতে ফারমু?', district='Sunamganj', crop=Crop('Boro Rice'),
                 gold_doc='FFWC-HAOR-01', dialect='Sylheti', kind='topical'),
    HoldoutProbe(question='During the monsoon our haor stays under cloud all the time — which satellite can still spot flooded paddy land, and does it see more damage than people walking the fields?', district='Netrokona', crop=Crop('Boro Rice'),
                 gold_doc='FFWC-HAOR-01', dialect='English', kind='topical'),
    HoldoutProbe(question='ঠান্ডা ঘরো আলুর লাখান বেগুনও রাখতাম চাইছিলাম, কিন্তু হুনছি বেশি ঠান্ডা অইলে বেগুনর গায়ে গাতা ফড়ি বীজ কালা অই যায় — কুন ডিগ্রির নিচে নামা যাইত না?', district=None, crop=Crop('Brinjal'),
                 gold_doc='BARI-BRINJAL-01', dialect='Sylheti', kind='cross_doc'),
    HoldoutProbe(question='ইবার বানর কুনু ডর নাই, বান্ধও ঠিক আছে — তাও মাড়ানির ফরে ধান ভালা করি না হুকাইয়া বস্তাত ভরলে কিতা ক্ষতি অইব?', district='Sunamganj', crop=Crop('Boro Rice'),
                 gold_doc='BRRI-BORO-01', dialect='Sylheti', kind='negation'),
    HoldoutProbe(question='How many middlemen hands does my chili pass through before it reaches a Dhaka shop, and how much of the final shop price do they keep between them?', district=None, crop=Crop('Green Chili'),
                 gold_doc='CPD-SYND-01', dialect='English', kind='topical'),
    HoldoutProbe(question='Faria ar Bepari ke bad diye amra kojon farmer mile direct arot e bechte pari ki bhabe?', district=None, crop=None,
                 gold_doc='CPD-SYND-01', dialect='Banglish', kind='paraphrase'),
    HoldoutProbe(question='কারওয়ান বাজারের আড়তদার কমিশন আর খাজনা বাবদ বেপারীর খরচের কত ভাগ নিয়ে নেয়, অথচ বাছাইয়ের পেছনে কিছু খরচ করে কি?', district='Dhaka Karwan Bazar', crop=None,
                 gold_doc='CPD-SYND-01', dialect='Standard Bangla', kind='topical'),
    HoldoutProbe(question="I grow vegetables near Cox's Bazar. Is there any collection centre that buys for the refugee camps, and how do they pay the money?", district="Cox's Bazar", crop=Crop('Brinjal'),
                 gold_doc='WFP-AGG-01', dialect='English', kind='topical'),
    HoldoutProbe(question='Which quality grades of potato will the WFP buying points take from a smallholder, and is their rate close to the wholesale rate?', district=None, crop=Crop('Cardinal Potato'),
                 gold_doc='WFP-AGG-01', dialect='English', kind='paraphrase'),
    HoldoutProbe(question='Hamar Kurigram ot oi WFP er koyta kendra ache re, ar oomra taka ki mobile ot dey?', district='Kurigram', crop=None,
                 gold_doc='WFP-AGG-01', dialect='Rangpuri', kind='topical'),
    HoldoutProbe(question='Why do small potato farmers like me never find space in the cold store while the traders and the plant owners seem to hold most of the bookings?', district=None, crop=Crop('Diamant Potato'),
                 gold_doc='BCSA-QUOTA-01', dialect='English', kind='topical'),
    HoldoutProbe(question='The cold store people doubled the seasonal rent this year. What is the new charge per kg, and what does it come to all-in up north?', district='Thakurgaon', crop=Crop('Cardinal Potato'),
                 gold_doc='BCSA-QUOTA-01', dialect='English', kind='paraphrase'),
    HoldoutProbe(question='Munshiganj e joto alu othe tar koto tuku himaghar e jayga pay? Baki alu gulor ki hoy?', district='Munshiganj', crop=Crop('Cardinal Potato'),
                 gold_doc='BCSA-QUOTA-01', dialect='Banglish', kind='topical'),
    HoldoutProbe(question='I cannot afford cold storage or a warehouse receipt this season. How do I still get a better price for my potatoes right now without going through the village Faria?', district=None, crop=Crop('Cardinal Potato'),
                 gold_doc='CPD-SYND-01', dialect='English', kind='negation'),
    HoldoutProbe(question='My brinjal is already sorted into Grade A and B after grading. Which institutional buyer weighs it on proper certified scales and pays a transparent contract rate?', district=None, crop=Crop('Brinjal'),
                 gold_doc='WFP-AGG-01', dialect='English', kind='cross_doc'),
    HoldoutProbe(question='Ek kg alu abad korte asole koto taka khoroch hoy? Harvest er shomoy bepari ra je dam dey sheta ki khorocher cheyeo kom?', district='Munshiganj', crop=Crop('Cardinal Potato'),
                 gold_doc='DAM-POT-PRICE-01', dialect='Banglish', kind='topical'),
    HoldoutProbe(question='Mui ekhon alu bechim naki thuya dim? Pore koto dam uthibe, kon mashot bechile beshi taka pamo?', district='Rangpur', crop=Crop('Diamant Potato'),
                 gold_doc='DAM-POT-PRICE-01', dialect='Rangpuri', kind='topical'),
    HoldoutProbe(question='ভরা মৌসুমে আলুর দাম পানির দরে নেমে যায়, অথচ ভাদ্র-আশ্বিন মাসে ঢাকায় নাকি অনেক চড়া দাম — কোন সময়ে বিক্রি করলে চাষি সবচেয়ে লাভবান হয়?', district=None, crop=Crop('Cardinal Potato'),
                 gold_doc='DAM-POT-PRICE-01', dialect='Standard Bangla', kind='paraphrase'),
    HoldoutProbe(question='Licensed gudame foshol joma rekhe receipt dekhaiya bank theke dhar neya jay shunchi — fosholer dam er koto bhag porjonto loan dey tara?', district=None, crop=None,
                 gold_doc='BB-WHR-01', dialect='Banglish', kind='topical'),
    HoldoutProbe(question='Warehouse receipt er bipode je loan dey, tar sud bochore koto percent ar taka ta kobe shodh korte hoy?', district=None, crop=None,
                 gold_doc='BB-WHR-01', dialect='Banglish', kind='topical'),
    HoldoutProbe(question='Dhan katar por shongshar ar shamner mousumer shar-beej er taka lage, kintu ekhoni bechle thokte hobe — foshol na beche hater taka pawar kono bebostha ache ki?', district=None, crop=Crop('Boro Rice'),
                 gold_doc='BB-WHR-01', dialect='Banglish', kind='paraphrase'),
    HoldoutProbe(question='UCB bank er krishi rin e naki kono jamanat lage na? Oder sud koto percent?', district=None, crop=None,
                 gold_doc='AGRI-FIN-01', dialect='Banglish', kind='topical'),
    HoldoutProbe(question='iFarmer kombani ta asole ki kore — khali taka dey, naki amar foshol o kine ney?', district=None, crop=None,
                 gold_doc='AGRI-FIN-01', dialect='Banglish', kind='topical'),
    HoldoutProbe(question='Before approving credit for a smallholder, what kind of proof do UCB and iFarmer look at instead of land papers?', district=None, crop=None,
                 gold_doc='AGRI-FIN-01', dialect='English', kind='paraphrase'),
    HoldoutProbe(question='Amar jomir dolil o nai, cold storage er warehouse receipt o nai — kono bandhok chara kom sude loan dibe emon bank ache ki?', district=None, crop=None,
                 gold_doc='AGRI-FIN-01', dialect='Banglish', kind='negation'),
    HoldoutProbe(question='BCSA cold storage e quota ar slot paile alu rekhe dibo bhabchi — August-September e chamber theke ber kore Dhaka-y bechle kg proti koto dam uthte pare?', district='Thakurgaon', crop=Crop('Cardinal Potato'),
                 gold_doc='DAM-POT-PRICE-01', dialect='Banglish', kind='cross_doc'),
    HoldoutProbe(question='আম পাকাবার জন্যে কার্বাইড দিলে কি হবি? হুনিচ্চি এডা নাকি সরকার মানা করিচে?', district=None, crop=None,
                 gold_doc='DAE-SAFE-01', dialect='Bogura (Varendri)', kind='topical'),
    HoldoutProbe(question='মাছ-তরকারিত ফরমালিন মিশালে আইনত কি দোষ? কোন আইনে ধরবি হামাক?', district=None, crop=None,
                 gold_doc='DAE-SAFE-01', dialect='Bogura (Varendri)', kind='topical'),
    HoldoutProbe(question='Holud ar dal e je holde rong meshay dokandar ra, oita khaile ki khoti hobe?', district=None, crop=None,
                 gold_doc='DAE-SAFE-01', dialect='Banglish', kind='paraphrase'),
    HoldoutProbe(question='বগুড়া থনে ঢাকাত সবজির ট্রাক গেলে যমুনা সেতুত টোল কত নাগে?', district='Bogura', crop=None,
                 gold_doc='DAM-TRANS-01', dialect='Bogura (Varendri)', kind='topical'),
    HoldoutProbe(question='হামরা দশজন চাষি মিলে এক ট্রাক ভরে মাল পাঠালে কেজি প্রতি ভাড়া কত কমে আসবি?', district='Bogura', crop=None,
                 gold_doc='DAM-TRANS-01', dialect='Bogura (Varendri)', kind='topical'),
    HoldoutProbe(question='Is it better to send fresh vegetables to the city after sunset, and why?', district=None, crop=None,
                 gold_doc='DAM-TRANS-01', dialect='English', kind='paraphrase'),
    HoldoutProbe(question='কার্ডিনাল আর ডায়মন্ড — কোন আলুডা বিদেশত পাঠানির জন্যে বেশি চলে?', district='Bogura', crop=Crop('Diamant Potato'),
                 gold_doc='BARI-POT-VAR-01', dialect='Bogura (Varendri)', kind='topical'),
    HoldoutProbe(question='কত মাপের আলু হলে A গ্রেড ধরা হবি? হামার আলুগুলা মাঝারি সাইজের।', district='Bogura', crop=Crop('Cardinal Potato'),
                 gold_doc='BARI-POT-VAR-01', dialect='Bogura (Varendri)', kind='topical'),
    HoldoutProbe(question='লাল খোসার যে আলুর জাতটা, ওইটার নাম কী আর কোন কোন জেলায় বেশি লাগায়?', district=None, crop=Crop('Cardinal Potato'),
                 gold_doc='BARI-POT-VAR-01', dialect='Standard Bangla', kind='paraphrase'),
    HoldoutProbe(question='হিমাগারত না থুয়ে কোন গ্রেডের আলু হাটত সাথে সাথে বেচে দেওয়া নাগবি?', district=None, crop=None,
                 gold_doc='BARI-POT-VAR-01', dialect='Bogura (Varendri)', kind='negation'),
    HoldoutProbe(question='ফড়িয়া-বেপারীক বাদ দিয়ে হামরা নিজেরাই যশোর থনে ঢাকাত ট্রাক পাঠালে পদ্মা সেতুর টোল কত দেওয়া নাগবি?', district='Jessore', crop=None,
                 gold_doc='DAM-TRANS-01', dialect='Bogura (Varendri)', kind='cross_doc'),
)

_DOC_IDS = {doc.doc_id for doc in KNOWLEDGE_DOCS}
assert all(p.gold_doc in _DOC_IDS for p in HOLDOUT_PROBES), "holdout probe references an unknown doc"
assert len({p.question for p in HOLDOUT_PROBES}) == len(HOLDOUT_PROBES), "duplicate holdout question"


class HoldoutReport(BaseModel):
    generated_at: str
    duration_ms: float
    probes: int
    top1_gold: float
    top3_gold: float
    by_kind: dict[str, dict[str, float]]
    by_dialect: dict[str, dict[str, float]]
    misses: list[dict[str, str]]


async def run_holdout_probe(probes: tuple[HoldoutProbe, ...] = HOLDOUT_PROBES) -> HoldoutReport:
    """Retrieval accuracy on the blind probes, offline (climatology weather), gold doc in top-1 / top-3 chunks."""
    from rag.crag_pipeline import CRAG_PIPELINE

    started = time.perf_counter()
    hits1: dict[str, list[int]] = defaultdict(list)
    hits3: dict[str, list[int]] = defaultdict(list)
    dialect1: dict[str, list[int]] = defaultdict(list)
    misses: list[dict[str, str]] = []
    token = NETWORK_BLACKOUT.set(True)
    try:
        for probe in probes:
            result = await CRAG_PIPELINE.run(probe.question, probe.district, probe.crop, top_k=5)
            docs = list(dict.fromkeys(chunk.doc_id for chunk in result.retrieval))
            top1, top3 = int(docs[:1] == [probe.gold_doc]), int(probe.gold_doc in docs[:3])
            hits1[probe.kind].append(top1)
            hits3[probe.kind].append(top3)
            dialect1[probe.dialect].append(top1)
            if not top1:
                misses.append({"kind": probe.kind, "gold": probe.gold_doc, "got": docs[0] if docs else "-",
                               "question": probe.question[:80]})
    finally:
        NETWORK_BLACKOUT.reset(token)

    def summary(buckets: dict[str, list[int]]) -> dict[str, dict[str, float]]:
        return {name: {"n": float(len(values)), "top1": round(sum(values) / len(values), 4)}
                for name, values in sorted(buckets.items())}

    all1 = [v for values in hits1.values() for v in values]
    all3 = [v for values in hits3.values() for v in values]
    by_kind = summary(hits1)
    for name, values in hits3.items():
        by_kind[name]["top3"] = round(sum(values) / len(values), 4)
    return HoldoutReport(
        generated_at=now_bdt().isoformat(), duration_ms=round((time.perf_counter() - started) * 1000, 1),
        probes=len(probes), top1_gold=round(sum(all1) / len(all1), 4), top3_gold=round(sum(all3) / len(all3), 4),
        by_kind=by_kind, by_dialect=summary(dialect1), misses=misses,
    )


_CACHE: dict[str, tuple[float, HoldoutReport]] = {}


async def get_holdout_report(max_age_s: float = 600.0) -> HoldoutReport:
    """Cached wrapper for the API, mirroring the metrics endpoint's 10-minute cache."""
    cached = _CACHE.get("report")
    if cached and time.monotonic() - cached[0] < max_age_s:
        return cached[1]
    report = await run_holdout_probe()
    _CACHE["report"] = (time.monotonic(), report)
    return report


if __name__ == "__main__":
    report = asyncio.run(run_holdout_probe())
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
