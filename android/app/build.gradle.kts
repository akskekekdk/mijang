plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.mijang.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.mijang.app"
        minSdk = 26
        targetSdk = 34
        // CI 빌드 번호를 버전으로 사용해 새 APK가 기존 앱 위에 업데이트 설치되도록 한다.
        versionCode = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
        versionName = "1.0.$versionCode"
    }

    signingConfigs {
        // 저장소에 포함된 고정 키: 어느 빌드든 같은 서명이라 덮어쓰기 설치가 된다.
        create("shared") {
            storeFile = file("mijang.keystore")
            storePassword = "android"
            keyAlias = "mijang"
            keyPassword = "android"
        }
    }

    buildTypes {
        debug { signingConfig = signingConfigs.getByName("shared") }
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("shared")
        }
    }

    sourceSets["main"].assets.srcDir("../../data")

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
