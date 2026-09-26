package com.mijang.app

import android.Manifest
import android.os.Build
import android.os.Bundle
import android.view.LayoutInflater
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.work.WorkInfo
import androidx.work.WorkManager

class MainActivity : ComponentActivity() {
    private lateinit var status: TextView
    private lateinit var content: LinearLayout
    private var loading = false

    private val askNotification =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) {
            Store.load(this)?.let { Notifier.show(this, it) }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        status = findViewById(R.id.status)
        content = findViewById(R.id.content)
        findViewById<Button>(R.id.refresh).setOnClickListener {
            UpdateWorker.runNow(this, forceFetch = true)
        }

        if (Build.VERSION.SDK_INT >= 33) askNotification.launch(Manifest.permission.POST_NOTIFICATIONS)

        WorkManager.getInstance(this).getWorkInfosForUniqueWorkLiveData(UpdateWorker.NOW)
            .observe(this) { infos ->
                loading = infos.any { it.state == WorkInfo.State.RUNNING || it.state == WorkInfo.State.ENQUEUED }
                render()
            }

        if (Store.load(this) == null) UpdateWorker.runNow(this, forceFetch = true)
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    private fun render() {
        val snapshot = Store.load(this)
        val watchlist = Store.watchlist(this)
        status.text = when {
            loading -> getString(R.string.loading)
            snapshot != null -> Format.asOf(snapshot.quotedAt) + " · 1시간마다 자동 갱신"
            else -> getString(R.string.empty)
        }
        content.removeAllViews()

        // 내가 담은 종목: 추천에서 빠져도 삭제 전까지 유지
        section(getString(R.string.watchlist) + if (watchlist.isEmpty()) "" else " ${watchlist.size}")
        if (watchlist.isEmpty()) note(getString(R.string.watch_empty))
        val recommended = snapshot?.stocks?.map { it.ticker }?.toSet() ?: emptySet()
        watchlist.forEach { w ->
            val quote = snapshot?.quotes?.get(w.ticker)
            row(Format.watchedLine(this, w, quote, w.ticker in recommended), getString(R.string.remove), true) {
                Store.removeWatch(this, w.ticker)
                render()
            }
        }

        if (snapshot == null) return
        section(getString(R.string.recommend))
        note("${snapshot.prediction.asOf} 종가까지 학습 · 향후 3개월 SPY(S&P 500)보다 오를 종목 예측\n" +
            snapshot.prediction.summary)
        val watched = watchlist.map { it.ticker }.toSet()
        Format.rows(this, snapshot.stocks, withScore = true).zip(snapshot.stocks).forEach { (line, stock) ->
            val isWatched = stock.ticker in watched
            row(line, getString(if (isWatched) R.string.added else R.string.add), !isWatched) {
                Store.addWatch(this, stock)
                render()
            }
        }
        note("\n" + getString(R.string.disclaimer))
    }

    private fun section(text: String) {
        val v = LayoutInflater.from(this).inflate(R.layout.item_section, content, false) as TextView
        v.text = text
        content.addView(v)
    }

    private fun note(text: String) {
        val v = LayoutInflater.from(this).inflate(R.layout.item_note, content, false) as TextView
        v.text = text
        content.addView(v)
    }

    private fun row(text: CharSequence, action: String, enabled: Boolean, onClick: () -> Unit) {
        val v = LayoutInflater.from(this).inflate(R.layout.item_stock, content, false)
        v.findViewById<TextView>(R.id.text).text = text
        v.findViewById<Button>(R.id.action).apply {
            this.text = action
            isEnabled = enabled
            setOnClickListener { onClick() }
        }
        content.addView(v)
    }
}
