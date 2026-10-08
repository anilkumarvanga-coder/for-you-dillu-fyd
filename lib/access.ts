/** At most two explicitly approved Clerk identities. Misconfiguration denies all. */
export function allowedClerkUsers(value: string | undefined): string[] {
 const users=[...new Set((value??'').split(',').map(x=>x.trim()).filter(Boolean))];
 return users.length>0 && users.length<=2 && users.every(x=>/^user_[A-Za-z0-9]+$/.test(x)) ? users : [];
}
