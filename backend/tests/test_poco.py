from pathlib import Path

from archdiscovery.analyzer.syntax.analyze import analyze_syntax


def test_poco_routes_and_external_calls(tmp_path: Path) -> None:
    (tmp_path / "main.cpp").write_text(
        "#include <Poco/Net/HTTPRequestHandler.h>\n"
        "class PostgresStore { public: void createUser() {} };\n"
        "class RedisCache { public: void set(const char*, const char*) {} };\n"
        "class RabbitMQProducer { public: void publish(const char*) {} };\n"
        "class ApiHandler : public Poco::Net::HTTPRequestHandler {\n"
        "public:\n"
        "  explicit ApiHandler(PostgresStore& store, RedisCache& cache, RabbitMQProducer& producer)\n"
        "      : store_(store), cache_(cache), producer_(producer) {}\n"
        "  void dispatch(const char* method, const std::vector<std::string>& segments) {\n"
        '    if (method == "POST" && segments.size() == 1 && segments[0] == "users") {\n'
        "      createUser(); return;\n"
        "    }\n"
        "  }\n"
        "  void createUser() {\n"
        "    store_.createUser();\n"
        '    cache_.set("key", "value");\n'
        '    producer_.publish("user.created");\n'
        "  }\n"
        "private:\n"
        "  PostgresStore& store_;\n"
        "  RedisCache& cache_;\n"
        "  RabbitMQProducer& producer_;\n"
        "};\n",
        encoding="utf-8",
    )
    result = analyze_syntax(tmp_path, tmp_path / "syntax.json")

    assert len(result["handlers"]) == 1
    handler = result["handlers"][0]
    assert handler["method"] == "POST"
    assert handler["path"] == "/users"
    assert handler["handler"]["symbol"] == "createUser"
    assert handler["handler"]["language"] == "cpp"

    kinds = {item["output"]["kind"] for item in result["outbound_calls"]}
    assert kinds == {"postgresql", "redis", "rabbitmq"}
