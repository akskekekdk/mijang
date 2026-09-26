package com.mijang.app

import android.content.Context

object Store {
    private const val PREFS = "mijang"
    private const val KEY = "snapshot_v2"

    fun load(context: Context): Snapshot? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)
            ?.let { runCatching { Snapshot.fromJson(it) }.getOrNull() }

    fun save(context: Context, snapshot: Snapshot) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY, snapshot.toJson()).apply()
    }
}
