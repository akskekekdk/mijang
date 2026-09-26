package com.mijang.app

import android.content.Context
import java.io.File

object Store {
    private const val PREFS = "mijang"
    private const val KEY = "snapshot_v3"
    private const val WATCH = "watchlist"

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun load(context: Context): Snapshot? =
        prefs(context).getString(KEY, null)?.let { runCatching { Snapshot.fromJson(it) }.getOrNull() }

    fun save(context: Context, snapshot: Snapshot) {
        prefs(context).edit().putString(KEY, snapshot.toJson()).apply()
    }

    private fun reportFile(context: Context) = File(context.filesDir, "predictions.json")

    fun saveReport(context: Context, json: String) {
        val tmp = File(context.filesDir, "predictions.json.tmp")
        tmp.writeText(json)
        tmp.renameTo(reportFile(context))
    }

    /** 근거 화면용 전체 예측 파일. */
    fun report(context: Context): Report? =
        reportFile(context).takeIf { it.exists() }?.let { runCatching { Report.parse(it.readText()) }.getOrNull() }

    fun watchlist(context: Context): List<Watched> =
        prefs(context).getString(WATCH, null)?.let { runCatching { Watched.listFromJson(it) }.getOrNull() }
            ?: emptyList()

    private fun saveWatchlist(context: Context, list: List<Watched>) {
        prefs(context).edit().putString(WATCH, Watched.listToJson(list)).apply()
    }

    fun addWatch(context: Context, ticker: String, name: String, price: Double) {
        val list = watchlist(context)
        if (list.none { it.ticker == ticker }) {
            saveWatchlist(context, list + Watched(ticker, name, System.currentTimeMillis(), price))
        }
    }

    fun removeWatch(context: Context, ticker: String) {
        saveWatchlist(context, watchlist(context).filterNot { it.ticker == ticker })
    }
}
