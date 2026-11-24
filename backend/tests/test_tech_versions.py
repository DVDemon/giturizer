from pathlib import Path

from archdiscovery.pipeline.tech_detect import detect_technologies


def versions(tmp_path: Path) -> dict[str, str | None]:
    return {tech.name: tech.version for tech in detect_technologies(tmp_path)}


def test_versions_from_images_and_dockerfile(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text(
        "services:\n"
        "  db:\n"
        "    image: postgres:14\n"
        "  mongo:\n"
        "    image: mongo:5.0.31-focal\n"
        "  cache:\n"
        "    image: valkey/valkey:8.1.1-alpine\n",
        encoding="utf-8",
    )
    (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")

    found = versions(tmp_path)

    assert found["PostgreSQL"] == "14"
    assert found["MongoDB"] == "5.0.31"
    assert found["Valkey"] == "8.1.1"
    assert found["Python"] == "3.12"


def test_versions_from_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"express": "^4.18.2"}, "engines": {"node": ">=20"}}',
        encoding="utf-8",
    )

    found = versions(tmp_path)

    assert found["express"] == "4.18.2"
    assert found["Node.js"] == "20"


def test_versions_from_python_manifests(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("fastapi==0.115.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["httpx>=0.27"]\n' 'requires-python = ">=3.11"\n',
        encoding="utf-8",
    )

    found = versions(tmp_path)

    assert found["fastapi"] == "0.115.0"
    assert found["httpx"] == "0.27"
    assert found["Python"] == "3.11"


def test_versions_from_jvm_and_dotnet_manifests(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text(
        "<project>"
        "<properties><java.version>17</java.version></properties>"
        "<dependencies><dependency>"
        "<groupId>org.springframework</groupId><artifactId>spring-core</artifactId>"
        "<version>6.1.0</version></dependency></dependencies>"
        "</project>",
        encoding="utf-8",
    )
    (tmp_path / "app.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk">'
        "<PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>"
        '<ItemGroup><PackageReference Include="Newtonsoft.Json" Version="13.0.3" />'
        "</ItemGroup></Project>",
        encoding="utf-8",
    )

    found = versions(tmp_path)

    assert found["Java"] == "17"
    assert found["spring-core"] == "6.1.0"
    assert found[".NET"] == "8.0"
    assert found["Newtonsoft.Json"] == "13.0.3"


def test_versions_from_go_and_gradle(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text(
        "module demo\n\ngo 1.22\n\nrequire github.com/gin-gonic/gin v1.9.1\n",
        encoding="utf-8",
    )
    (tmp_path / "build.gradle").write_text(
        "dependencies {\n    implementation 'org.slf4j:slf4j-api:2.0.9'\n}\n",
        encoding="utf-8",
    )

    found = versions(tmp_path)

    assert found["Go"] == "1.22"
    assert found["github.com/gin-gonic/gin"] == "1.9.1"
    assert found["org.slf4j:slf4j-api"] == "2.0.9"


def test_versions_from_cmake(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text(
        "find_package(userver 2.5 COMPONENTS core REQUIRED)\n", encoding="utf-8"
    )
    library = tmp_path / "jwt-cpp"
    library.mkdir()
    (library / "CMakeLists.txt").write_text(
        "write_basic_package_version_file(config.cmake VERSION 0.7.1 COMPATIBILITY AnyNewerVersion)\n",
        encoding="utf-8",
    )

    found = versions(tmp_path)

    assert found["userver"] == ">=2.5"
    assert found["jwt-cpp"] == "0.7.1"


def test_deduplicates_same_name(tmp_path: Path) -> None:
    (tmp_path / "main.cpp").write_text("#include <jwt-cpp/jwt.h>\n", encoding="utf-8")
    library = tmp_path / "jwt-cpp"
    library.mkdir()
    (library / "jwt.h").write_text("", encoding="utf-8")

    technologies = detect_technologies(tmp_path)
    names = [tech.name for tech in technologies]

    assert names.count("jwt-cpp") == 1


def test_versions_from_tool_files_and_cmake_settings(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("3.12.5\n", encoding="utf-8")
    (tmp_path / ".nvmrc").write_text("20.11.0\n", encoding="utf-8")
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.22)\n" "set(CMAKE_CXX_STANDARD 20)\n",
        encoding="utf-8",
    )
    (tmp_path / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    found = versions(tmp_path)

    assert found["Python"] == "3.12.5"
    assert found["Node.js"] == "20.11.0"
    assert found["CMake"] == ">=3.22"
    assert found["C++"] == "20"


def test_versions_from_wrappers_and_pom_parent(tmp_path: Path) -> None:
    gradle = tmp_path / "gradle" / "wrapper"
    gradle.mkdir(parents=True)
    (gradle / "gradle-wrapper.properties").write_text(
        "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.7-bin.zip\n",
        encoding="utf-8",
    )
    maven = tmp_path / ".mvn" / "wrapper"
    maven.mkdir(parents=True)
    (maven / "maven-wrapper.properties").write_text(
        "distributionUrl=https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.9/apache-maven-3.9.9-bin.zip\n",
        encoding="utf-8",
    )
    (tmp_path / "pom.xml").write_text(
        "<project><parent>"
        "<groupId>org.springframework.boot</groupId>"
        "<artifactId>spring-boot-starter-parent</artifactId>"
        "<version>3.3.0</version></parent></project>",
        encoding="utf-8",
    )

    found = versions(tmp_path)

    assert found["Gradle"] == "8.7"
    assert found["Maven"] == "3.9.9"
    assert found["spring-boot-starter-parent"] == "3.3.0"
