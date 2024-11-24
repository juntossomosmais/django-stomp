.PHONY: tests test_activemq test_rabbitmq

_down:
	docker compose down --remove-orphans # prevent port binding conflict

test_activemq:
	docker compose up --detach integration-tests-active-mq
	docker compose exec --interactive integration-tests-active-mq ./scripts/start-tests.sh
	$(MAKE) _down

test_rabbitmq:
	docker compose up --detach integration-tests-rabbit-mq
	docker compose exec --interactive integration-tests-rabbit-mq ./scripts/start-tests.sh
	$(MAKE) _down

test: test_activemq test_rabbitmq
