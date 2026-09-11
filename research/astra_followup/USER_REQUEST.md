# Advisory request and execution mandate

User explicitly requested a separate `gpt-6-astra` agent with `high` reasoning
effort, prompted with:

> i am performing bundle adjustment experiment and need guidance in which direction i could research to do something novel. give me some ideas i can ask an agent to try out. even rough directions in which the agent can research in. can be methods from physics other modeling of the problem (math optiimization etc) you name it.

The user then instructed the parent agent to implement and test the suggested
directions and report suggestions and intermediate findings in chat. The
adviser was spawned as `novel_ba_directions`, with the requested model/effort,
and given the completed research-feedback report to avoid repeating old work.
Its advisory artifacts live in `advice/`; the parent owns implementations and
serial benchmarks. The adviser does not change solver code or run benchmarks.

Parent source baseline: `78fc32e8f33f54eaf46b5298032ef7ce46d75620`.
Original production Eta2 and previous experiments remain unchanged. New work
is isolated on `research/astra-guided-ba`. CPU mechanism tests are not GPU
Eta2/Caspar comparisons; production promotion requires a separate matched test.
