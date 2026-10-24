/** The five recorded dialect questions the backend ships (`edge_node/bangla_voice.VOICE_PRESETS`). */
export interface StoryPreset {
  id: string;
  farmer: string;
  place: string;
  dialect: string;
  question: string;
  english: string;
}

export const STORY_PRESETS: StoryPreset[] = [
  {
    id: "rangpur_potato_distress", farmer: "Rahim Mia", place: "Mithapukur, Rangpur", dialect: "Rangpuri",
    question: "এলা বেচমু না হিমাগারত থুমু?", english: "Should I sell now, or keep them in cold storage?",
  },
  {
    id: "bogura_chili_syndicate", farmer: "Karim", place: "Sariakandi, Bogura", dialect: "Bogura (Varendri)",
    question: "সিন্ডিকেট ছাড়া ক্যাংকা করি সরাসরি ব্যাচমু?", english: "How do I sell directly, without the syndicate?",
  },
  {
    id: "sunamganj_haor_flood", farmer: "Abdul", place: "Tahirpur, Sunamganj", dialect: "Sylheti",
    question: "অখন কাটমু নি?", english: "Should I cut it now?",
  },
  {
    id: "munshiganj_cold_storage", farmer: "A farmer", place: "Tongibari, Munshiganj", dialect: "Standard Bangla",
    question: "সমিতির মাধ্যমে হিমাগারে জায়গা পাওয়া যাবে?", english: "Can we get cold-storage space through our cooperative?",
  },
  {
    id: "jessore_brinjal_pooling", farmer: "A farmer", place: "Jhikargacha, Jessore", dialect: "Standard Bangla",
    question: "পাশের গ্রামের চাষিদের সাথে মিলে ঢাকায় পাঠাতে চাই।", english: "I want to send it to Dhaka together with farmers from the next village.",
  },
];

export const RAHIM = STORY_PRESETS[0];
export const ABDUL = STORY_PRESETS[2];

export const TEAM: { name: string; role: string; country: string }[] = [
  { name: "Tanvir Hossin", role: "Team Lead", country: "Bangladesh" },
  { name: "Md. Omar Faruk", role: "AI/ML Engineer", country: "Bangladesh" },
  { name: "Md. Abdur Rahman", role: "Full-Stack & Backend Developer", country: "Bangladesh" },
  { name: "Mohammed Mahmud Parvez", role: "Full-Stack Developer", country: "Bangladesh" },
  { name: "Md. Morsalin", role: "Full-Stack & Backend Developer", country: "Bangladesh" },
  { name: "Md Rifat", role: "Domain Expert (Network Engineering)", country: "USA" },
];
