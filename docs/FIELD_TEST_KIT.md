# Field-test kit: putting KrishiNexus OS in front of real farmers

No study with farmers has been run yet. This kit is the plan for the first one. Report whatever it finds, including
"not useful" answers. Never edit, pick or invent results.

## 1. Who and where

- **Five farmers** in Shibganj, Bogura (potato and green chili), the area the seeded accounts and pools cover.
- **One agriculture officer** from the Department of Agricultural Extension (a Sub-Assistant Agriculture Officer of
  the union), who can judge whether the advice is agronomically sound.
- **About 45 minutes per farmer**, at their home or the union office. Pay for their time.
- **Bring:**
  - an Android phone with Chrome (online voice);
  - a laptop running the kiosk with the network toggle on "Offline edge" (offline voice through the kiosk's Whisper);
  - printed copies of the consent script and the score sheet.

## 2. Consent (read aloud before anything else)

> আমরা একটি পরীক্ষামূলক অ্যাপ দেখাচ্ছি যা আলু ও মরিচ বিক্রির পরামর্শ দেয়। আপনার কথা শুধু এই পরীক্ষার জন্য ব্যবহার হবে।
> নাম ও ফোন নম্বর রাখা হবে না। আপনি যেকোনো সময় থামতে পারেন। আপনার কথা ছাপানোর আগে আমরা আপনার অনুমতি নেব।
> আপনি কি রাজি?

> We are testing an app that gives advice on selling potatoes and chili. What you say is used only for this test.
> Your name and phone number are not kept. You can stop at any time. We will ask before quoting you anywhere.
> Do you agree?

Write down "agreed" and the date. Do not record names on the score sheet; use F1–F5 and O1 for the officer.

## 3. Tasks (each farmer, in this order)

| # | Task | Done when |
|---|---|---|
| 1 | Log in with the farmer's demo account and agree to the in-app consent | The farmer app shows their name |
| 2 | Ask, in their own words, whether to sell today or store, with the price they were really offered | The farmer hears the spoken answer |
| 3 | Photograph a handful of their own potatoes or chili and grade it | A grade and certificate appear |
| 4 | Ask the same question with the network switched to "Offline edge" | An answer arrives without internet |
| 5 | Rate the answer in the app ("Was this advice useful?"), with a comment if they want | The app says thank you |

Do not help with a task unless the farmer is stuck for a minute. If you help, write that down: it counts as not done
unaided.

## 4. Score sheet (one per farmer)

| Question (ask in Bangla) | Answer |
|---|---|
| Task 1–5 done without help? | ✓ / ✗ for each |
| Did you understand the spoken answer? (পুরোপুরি / কিছুটা / না) | |
| Would you follow this advice? (হ্যাঁ / হয়তো / না) Why? | |
| Was anything wrong or confusing? | |
| Would you pay Tk 0.10 per kg to join a pooled truck? | |
| In-app rating (task 5): useful or not useful? | |
| Can we quote you, without your name? | হ্যাঁ / না |

**The officer (O1)** reads three of the answers and scores each: agronomically sound / partly / wrong, with a reason.

## 5. Success bar (set now, before the test)

- At least 4 of 5 farmers finish tasks 2 and 5 without help.
- At least 70% of in-app ratings are "useful".
- The officer rates no answer as "wrong".

Report the numbers that come out, whether or not they meet the bar.

## 6. After the test

1. Export the ratings: log in as the admin and open **Admin → Feedback** (`/admin/feedback`). The page shows the share
   rated useful and every comment, with personal details already removed. On the free hosted demo the disk is wiped
   whenever the service sleeps, so read the page right after each session; the paper score sheet is the lasting record.
2. Write the results into `docs/internal/MEMORY.md`, and into the pitch: tasks done, understood, would follow, the officer's scores,
   and quotes only from farmers who agreed.
3. Fix the top problem they hit before the showcase, and say so in the pitch.
