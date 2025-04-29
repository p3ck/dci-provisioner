#!/bin/sh

if [ -z "$RQ_QUEUE" ]; then
	RQ_QUEUE="lab1"
fi

if [ -z "$REDIS_HOST" ]; then
	REDIS_HOST="redis"
fi

rq worker --url redis://$REDIS_HOST/ --path /opt/dci-provisioner/api --results-ttl 86400 $RQ_QUEUE
