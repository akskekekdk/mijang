package com.mijang.app

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import androidx.core.content.pm.PackageInfoCompat
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** GitHub Releases 의 최신 APK로 앱을 업데이트한다. */
object Updater {
    private const val BASE = "https://github.com/akskekekdk/mijang/releases/latest/download/"
    const val APK_URL = BASE + "mijang.apk"
    private const val VERSION_URL = BASE + "version.json"

    data class Release(val versionCode: Long, val versionName: String)

    fun parse(json: String): Release {
        val o = JSONObject(json)
        return Release(o.getLong("versionCode"), o.getString("versionName"))
    }

    fun installedVersion(context: Context): Long =
        PackageInfoCompat.getLongVersionCode(context.packageManager.getPackageInfo(context.packageName, 0))

    /** 설치된 것보다 새 버전이 있으면 그 정보를, 없으면 null. 네트워크에서 호출할 것. */
    fun check(context: Context): Release? {
        val latest = parse(Net.get(VERSION_URL))
        return latest.takeIf { it.versionCode > installedVersion(context) }
    }

    /** APK를 캐시 폴더에 받는다. 네트워크에서 호출할 것. */
    fun download(context: Context): File {
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val tmp = File(dir, "mijang.apk.part")
        val conn = URL(APK_URL).openConnection() as HttpURLConnection
        conn.instanceFollowRedirects = true
        conn.connectTimeout = 15_000
        conn.readTimeout = 60_000
        try {
            conn.inputStream.use { input -> tmp.outputStream().use { input.copyTo(it) } }
        } finally {
            conn.disconnect()
        }
        val apk = File(dir, "mijang.apk")
        apk.delete()
        check(tmp.renameTo(apk)) { "APK 저장 실패" }
        return apk
    }

    /**
     * 설치 화면을 연다. "이 출처의 앱 설치"가 꺼져 있으면 그 설정 화면을 먼저 열고 false 를 돌려준다
     * (허용한 뒤 업데이트 버튼을 다시 누르면 된다).
     */
    fun install(activity: Activity, apk: File): Boolean {
        if (Build.VERSION.SDK_INT >= 26 && !activity.packageManager.canRequestPackageInstalls()) {
            activity.startActivity(
                Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${activity.packageName}"))
            )
            return false
        }
        val uri = FileProvider.getUriForFile(activity, "${activity.packageName}.updates", apk)
        activity.startActivity(
            Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, "application/vnd.android.package-archive")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        )
        return true
    }

    /** 앱 안 설치가 안 될 때: 브라우저로 APK 링크 열기. */
    fun openInBrowser(activity: Activity) {
        activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(APK_URL)))
    }
}
