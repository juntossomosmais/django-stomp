.PHONY: tests test_activemq test_rabbitmq

test_activemq:
	docker compose exec integration-tests-active-mq ./scripts/start-tests.sh

test_rabbitmq:
	docker compose exec integration-tests ./scripts/start-tests.sh

test: test_activemq test_rabbitmq
