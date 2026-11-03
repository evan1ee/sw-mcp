# core-service

Long-lived Python service, one per Windows user. It hosts the tool handlers, the job queue, the execution journal, the project store and the add-in connections. MCP front-ends connect to it over a user-only named pipe. See ADR-041.
