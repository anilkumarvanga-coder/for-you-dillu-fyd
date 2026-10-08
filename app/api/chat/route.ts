// Old unauthenticated-by-Clerk route intentionally retired.
export async function POST(){return Response.json({error:'Use the Clerk-authenticated /api/study/chat endpoint.'},{status:410});}
