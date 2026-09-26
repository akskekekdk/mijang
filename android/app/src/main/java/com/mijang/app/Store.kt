package com.mijang.app

import android.content.Context

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

    fun watchlist(context: Context): List<Watched> =
        prefs(context).getString(WATCH, null)?.let { runCatching { Watched.listFromJson(it) }.getOrNull() }
            ?: emptyList()

    private fun saveWatchlist(context: Context, list: List<Watched>) {
        prefs(context).edit().putString(WATCH, Watched.listToJson(list)).apply()
    }

    fun addWatch(context: Context, stock: Stock) {
        val list = watchlist(context)
        if (list.none { it.ticker == stock.ticker }) {
            saveWatchlist(context, list + Watched(stock.ticker, stock.name, System.currentTimeMillis(), stock.price))
        }
    }

    fun removeWatch(context: Context, ticker: String) {
        saveWatchlist(context, watchlist(context).filterNot { it.ticker == ticker })
    }
}
