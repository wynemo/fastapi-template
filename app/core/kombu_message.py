from kombu import Connection, Exchange, Queue
from kombu.entity import PERSISTENT_DELIVERY_MODE
from kombu.pools import producers
from kombu.mixins import ConsumerMixin

from app.core.log import logger

connection = Connection('redis://127.0.0.1:6379/3', transport_options={ #todo protocol
    'interval_start': 0,
    'interval_step': 1,
    'interval_max': 5,
    'max_retries': 3,
    'timeout': 5
})
exchange_name = 'something' #todo


def publish(msg, routing_key):
    # type: (object, str) -> None
    logger.info('publish {msg} {routing_key}'.format(msg=msg, routing_key=routing_key))
    exchange = Exchange(name=exchange_name, durable=True, type='topic', delivery_mode=PERSISTENT_DELIVERY_MODE)
    with producers[connection].acquire(block=True, timeout=10) as producer:
        producer.publish(
            msg,
            exchange=exchange,
            routing_key=routing_key,
            serializer='json'
        )

class Worker(ConsumerMixin):
    def __init__(self, _connection):
        self.connection = _connection
        self.queue_cbs = {}
        self.exchange = Exchange(name=exchange_name, durable=True, type='topic', delivery_mode=PERSISTENT_DELIVERY_MODE)

    def get_consumers(self, Consumer, channel):
        consumers = []
        for _queue, _cb in self.queue_cbs.items():
            try:
                _consumer = Consumer(queues=_queue, callbacks=[_cb])
            except Exception as e:
                logger.exception(e)
            else:
                consumers.append(_consumer)
        return consumers

    def on(self, routing_key, callback):
        queue_name = "usm.%s.%s.%s" % (routing_key, callback.__module__, callback.__name__)
        logger.debug('queue {queue_name}'.format(queue_name=queue_name))
        queue = Queue(queue_name, exchange=self.exchange, routing_key=routing_key)
        queue.maybe_bind(self.connection)
        queue.declare()
        self.queue_cbs[queue] = callback

    def on_connection_revived(self):
        logger.debug('on_connection_revived')

		
if __name__ == '__main__':
    def foo_cb(body, message):
        print('foo cb', body)
        message.ack()

    rabbit_url = 'redis://127.0.0.1:6379/3'
    with Connection(rabbit_url, heartbeat=4) as conn:
        worker = Worker(conn)
        worker.on('foo.test', foo_cb)
        article = {'title': 'No cellular coverage on the tube for 2012',
                   'ingress': 'yadda yadda yadda3'}
        publish(article, 'foo.test')
        worker.run()

