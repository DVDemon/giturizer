from pathlib import Path

from archdiscovery.analyzer.syntax.analyze import analyze_syntax


def test_classifies_database_cache_storage_and_messaging(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "import redis\n"
        "import psycopg\n"
        "import boto3\n"
        "import pika\n"
        "from kafka import KafkaProducer\n"
        "from fastapi import APIRouter\n"
        'router = APIRouter(prefix="/orders")\n'
        '@router.post("/{order_id}/pay")\n'
        "async def pay(order_id: str):\n"
        '    redis_client.get("order:" + order_id)\n'
        '    db.execute("update orders set paid=true")\n'
        '    s3.put_object(Bucket="billing", Key="invoice.pdf")\n'
        '    channel.basic_publish(exchange="", routing_key="paid", body=b"x")\n'
        '    producer.send("paid-orders", b"x")\n',
        encoding="utf-8",
    )
    result = analyze_syntax(tmp_path, tmp_path / "syntax.json")
    kinds = {item["output"]["kind"] for item in result["outbound_calls"]}
    assert kinds == {"redis", "postgresql", "s3", "rabbitmq", "kafka"}
    assert result["stats"]["outbound_calls"] == 5
