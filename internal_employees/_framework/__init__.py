"""
Shared foundation for internal AI employee packages.

Everything in here is behaviour that is genuinely identical across
employees: how settings are read from the environment, how we talk HTTP
to PocketBase, the mirror of the server's action denylist, and the poll
loop. Anything specific to one employee (which collections it touches,
what it drafts, when it escalates) stays in that employee's own package.

The server (synkra-os ai_jobs.pb.js) remains the authority on what an AI
is allowed to do; the copies here are advisory mirrors so a worker fails
fast instead of burning a round trip.
"""
