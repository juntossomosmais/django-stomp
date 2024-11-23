.PHONY: tests test_activemq test_rabbitmq

test_activemq:
	docker compose up --abort-on-container-exit integration-tests-active-mq
	docker compose down --remove-orphans

test_rabbitmq:
	docker compose up --abort-on-container-exit integration-tests
	docker compose down --remove-orphans

test: test_activemq test_rabbitmq
