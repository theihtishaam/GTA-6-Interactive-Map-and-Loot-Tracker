const missionTypes = {
  story: "Story missions",
  optional: "Optional missions",
  stranger: "Strangers & Freaks",
  side: "Side tasks",
  discovery: "Discovered missions",
};

export function activityType(entry) {
  if (entry.category === "landmark") return entry.type || "";
  if (typeof entry.subcategory === "string" && entry.subcategory.trim()) return entry.subcategory.trim();
  if (entry.category === "mission" && Object.hasOwn(missionTypes, entry.kind)) return missionTypes[entry.kind];
  if (entry.collectibleSet) return entry.collectibleSet;
  if (entry.confidence === "personal") return "Personal pins";
  if (["lead", "reported", "area"].includes(entry.confidence)) return "Community reports";
  return "";
}
