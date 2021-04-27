# Aries Agent Demo

This folder contains a docker script that run several Aries agents (currently 2 aca-py and 2 afgo) to support manual testing of the agent api and backchannel.

To run the agents, first make sure you are running a local von-network and tails server (same as if you were running the test harness), and then:

```bash
docker-compose -f docker-compose-demo.yml up
```

To stop the agents, `<CTRL-C>` in the above shell and then run:

```bash
docker-compose -f docker-compose-demo.yml rm
```

When the agents are running you have access to the following URLs and ports:


| Agent | Bachchannel | Backchannel Port | Admin API (Swagger)           |
| ----- | ----------- | ---------------- | --------------------          |
| Acme  | acapy-main  | 9010             | http://localhost:9012/api/doc |
| Bob   | acapy-main  | 9020             | http://localhost:9022/api/doc |
| Faber | afgo-master | 9030             | http://localhost:9080/openapi |
| Alice | afgo-master | 9040             | http://localhost:9090/openapi |
