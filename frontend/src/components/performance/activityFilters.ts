export function matchesSenderSearch(sender: { sender_name: string; sender_id: number }, query: string): boolean {
  const normalize = (value: string) => value.normalize("NFKC").toLocaleLowerCase().trim();
  const terms = normalize(query).split(/\s+/).filter(Boolean);
  const identity = normalize(`${sender.sender_name} ${sender.sender_id}`);
  return terms.every((term) => identity.includes(term));
}

export const channelLabel = (name: string) => name || "Unspecified channel";
