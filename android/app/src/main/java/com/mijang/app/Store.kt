package com.mijang.app

import android.content.Context

object Store {
    private const val PREFS = "mijang"
    private const val KEY = "snapshot"

    fun load(context: Context): Snapshot? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)
            ?.let { runCatching { Snapshot.fromJson(it) }.getOrNull() }

    fun save(context: Context, snapshot: Snapshot) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY, snapshot.toJson()).apply()
    }

    /** assets/universe.txt → {티커: 한글이름} (저장소의 data/universe.txt 와 같은 파일). */
    fun universe(context: Context): Map<String, String> =
        context.assets.open("universe.txt").bufferedReader().useLines { lines ->
            lines.map { it.substringBefore('#').trim() }
                .filter { it.isNotEmpty() }
                .associate { line ->
                    val ticker = line.substringBefore(' ').uppercase()
                    ticker to line.substringAfter(' ', ticker).trim()
                }
        }
}
