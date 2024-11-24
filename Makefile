.PHONY: lint test_activemq test_rabbitmq tests check

_down:
	docker compose down --remove-orphans # prevent port binding conflict

lint: _down
	docker compose up --detach lint-formatter
	docker compose exec --interactive lint-formatter ./scripts/start-formatter-lint.sh
	$(MAKE) _down

test_activemq: _down
	docker compose up --detach integration-tests-active-mq
	docker compose exec --interactive integration-tests-active-mq ./scripts/start-tests.sh
	$(MAKE) _down

test_rabbitmq: _down
	docker compose up --detach integration-tests-rabbit-mq
	docker compose exec --interactive integration-tests-rabbit-mq ./scripts/start-tests.sh
	$(MAKE) _down

test: test_activemq test_rabbitmq

check: lint test
