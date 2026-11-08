// SPDX-FileCopyrightText: 2026 Beomjoon Kim
// SPDX-License-Identifier: AGPL-3.0-only
import java.net.URI
import java.security.MessageDigest

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// 데스크톱 앱과 같은 소스를 쓴다: 저장소 최상위의 Python 모듈·web·skills를 빌드할 때 복사해 넣는다.
val repoRoot: File = rootDir.parentFile
val appVersion: String = Regex("""APP_VERSION = "([0-9.]+)"""")
    .find(File(repoRoot, "version.py").readText())!!.groupValues[1]
val versionParts = appVersion.split(".").map { it.toInt() }

val sharedPythonDir = layout.buildDirectory.dir("generated/sharedPython")
val sharedAssetsDir = layout.buildDirectory.dir("generated/sharedAssets")

val syncSharedPython by tasks.registering(Sync::class) {
    from(repoRoot) {
        include(
            "agent.py", "ai_memory.py", "api.py", "attachments.py", "certs.py", "documents.py", "main.py",
            "mcp_client.py", "office_mcp.py", "paper_mcp.py", "notion_mcp.py", "firecrawl_mcp.py",
            "po_note.py", "sherpa_capi.py", "storage.py", "stt.py", "updates.py", "version.py",
            // 1.10: 커넥터·연결·도구 창
            "connectors.py", "oauth.py", "privacy.py", "secret_store.py", "workspace_api.py",
            "github_mcp.py", "google_mcp.py",
            // 1.10: 연구 워크스페이스
            "research_library.py", "research_mcp.py", "rag.py", "vector_store.py",
            // 1.10: 통합 메모리·인계·동기화
            "memory_store.py", "memory_mcp.py", "handoff.py", "sync.py",
            // 1.12: 플러그인(Knowledge Work Plugins)
            "plugins.py",
            // 1.13: 브라우저(웹페이지 뷰는 MainActivity가 만든다)
            "browser.py", "browser_api.py",
            // 1.14: 논문 읽기(PDF.js 화면은 web/vendor/pdfjs)
            "paper.py", "paper_api.py",
            // 1.18: Code 화면의 터미널, SSH 원격 작업 폴더(안드로이드에서는 쓸 수 없음으로 표시. ssh_remote.py는 paramiko라 데스크톱 전용)
            "terminal.py", "remote_fs.py", "remote_client.py", "remote_helper.py", "ssh_api.py",
            // 1.10: 에이전트 자동화(안드로이드에서는 쓸 수 없음으로 표시)·관측
            "runner_mcp.py", "telemetry.py", "evals.py",
            // 1.15: 화면 이벤트 큐(B1), POSCHAT Code(안드로이드는 열기·편집·저장·묻기만, Git·실행은 막는다)
            "ui_events.py", "code_api.py", "code_workspace.py", "code_diff.py", "code_git.py", "code_runner.py",
            // 1.16: POSCHAT Lab(안드로이드는 기록 보기·가져오기·그래프만, 실행은 막는다), Code 에이전트(PC 전용)
            "lab_store.py", "lab_results.py", "lab_api.py", "code_agent.py", "code_project.py", "browser_agent.py",
            // 1.17: Adaptive AI(라우터·검증기·엔진은 안드로이드에서도 돈다. 로컬 AI 실행기는 PC 전용이라 '쓸 수 없음')
            "local_ai.py", "adaptive_router.py", "quality_gate.py", "adaptive_engine.py", "adaptive_api.py", "adaptive_cost.py",
            // 1.18.1: 에이전트의 인터넷 도구(웹 검색·읽기·저자별 논문)
            "web_research.py",
        )
    }
    into(sharedPythonDir)
}

// PO노트 녹음의 로컬 음성 인식: sherpa-onnx 공식 AAR에서 C API 라이브러리와 ONNX Runtime만 꺼내 앱에 넣는다
// (Kotlin API는 신뢰도(토큰 확률)를 주지 않아서 Python sherpa_capi가 C API를 직접 부른다). 버전은 sherpa_capi.VERSION과 같아야 한다.
val sherpaVersion = "1.13.8"
val sherpaAarSha256 = "633c24321e06b1fe79feafa03ea16cbc0f8a286641e2da3559bac91bdb13bd96"
val sherpaAar = layout.buildDirectory.file("downloads/sherpa-onnx-$sherpaVersion.aar")
val sherpaJniDir = layout.buildDirectory.dir("generated/sherpaJniLibs")

fun sha256(file: File): String = MessageDigest.getInstance("SHA-256")
    .digest(file.readBytes()).joinToString("") { b -> "%02x".format(b) }

val downloadSherpaOnnx by tasks.registering {
    val target = sherpaAar
    outputs.file(target)
    doLast {
        val file = target.get().asFile
        if (file.isFile && sha256(file) == sherpaAarSha256) return@doLast
        file.parentFile.mkdirs()
        val url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/v$sherpaVersion/sherpa-onnx-$sherpaVersion.aar"
        val part = File(file.path + ".part")
        URI(url).toURL().openStream().use { input -> part.outputStream().use { output -> input.copyTo(output) } }
        val actual = sha256(part)
        if (actual != sherpaAarSha256) {
            part.delete()
            throw GradleException("sherpa-onnx AAR SHA-256 불일치: $actual")
        }
        part.renameTo(file)
    }
}

val syncSherpaJniLibs by tasks.registering(Sync::class) {
    dependsOn(downloadSherpaOnnx)
    from(sherpaAar.map { zipTree(it) }) {
        for (abi in listOf("arm64-v8a", "x86_64")) {  // defaultConfig.ndk.abiFilters와 같게
            include("jni/$abi/libsherpa-onnx-c-api.so", "jni/$abi/libonnxruntime.so")
        }
        eachFile { path = path.removePrefix("jni/") }
        includeEmptyDirs = false
    }
    into(sherpaJniDir)
}

val syncSharedAssets by tasks.registering(Sync::class) {
    from(File(repoRoot, "web")) { into("web") }
    from(File(repoRoot, "skills")) { into("skills") }
    from(File(repoRoot, "licenses")) { into("licenses") }
    from(repoRoot) { include("LICENSE", "THIRD_PARTY_NOTICES.md") }
    into(sharedAssetsDir)
}

android {
    namespace = "io.github.bj0322.poschat"
    compileSdk = 34

    defaultConfig {
        applicationId = "io.github.bj0322.poschat"
        minSdk = 24
        targetSdk = 34
        versionCode = versionParts[0] * 10000 + versionParts[1] * 100 + versionParts[2]
        versionName = appVersion
        ndk {
            // 휴대폰(arm64)과 에뮬레이터(x86_64)
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        // 모든 빌드를 같은 키로 서명해야 새 APK를 지우지 않고 덮어 설치할 수 있다.
        // 저장소에 들어 있는 공용 키이므로, 공개 배포(Play 스토어 등)에는 따로 보관한 키를 쓰세요.
        create("shared") {
            storeFile = file("poschat-shared.keystore")
            storePassword = "poschat"
            keyAlias = "poschat"
            keyPassword = "poschat"
        }
    }

    buildTypes {
        getByName("debug") {
            signingConfig = signingConfigs.getByName("shared")
        }
        getByName("release") {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("shared")
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    sourceSets["main"].assets.srcDir(sharedAssetsDir)
    sourceSets["main"].jniLibs.srcDir(sherpaJniDir)

    lint {
        checkReleaseBuilds = false  // CI 시간을 줄인다. 동작 검증은 에뮬레이터 계측 테스트가 한다
    }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        pip {
            install("-r", "requirements-android.txt")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir(sharedPythonDir)
        }
    }
}

tasks.named("preBuild") { dependsOn(syncSharedPython, syncSharedAssets, syncSherpaJniLibs) }
// Chaquopy·AGP의 소스 병합 작업이 복사보다 먼저 돌지 않게 한다.
tasks.configureEach {
    if (name.contains("Python", ignoreCase = true) && name.startsWith("merge")) dependsOn(syncSharedPython)
    if (name.endsWith("Assets") && name.startsWith("merge")) dependsOn(syncSharedAssets)
    if (name.endsWith("JniLibFolders") && name.startsWith("merge")) dependsOn(syncSherpaJniLibs)
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.2")
    implementation("androidx.webkit:webkit:1.11.0")

    androidTestImplementation("androidx.test:core:1.6.1")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test:rules:1.6.1")
}
