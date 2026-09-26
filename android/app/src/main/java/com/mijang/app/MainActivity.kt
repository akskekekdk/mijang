package com.mijang.app

import android.Manifest
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.work.WorkInfo
import androidx.work.WorkManager

class MainActivity : ComponentActivity() {
    private lateinit var status: TextView
    private lateinit var list: TextView

    private val askNotification =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) {
            Store.load(this)?.let { Notifier.show(this, it) }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        status = findViewById(R.id.status)
        list = findViewById(R.id.list)
        findViewById<Button>(R.id.refresh).setOnClickListener {
            UpdateWorker.runNow(this, forceRank = true)
        }

        if (Build.VERSION.SDK_INT >= 33) askNotification.launch(Manifest.permission.POST_NOTIFICATIONS)

        WorkManager.getInstance(this).getWorkInfosForUniqueWorkLiveData(UpdateWorker.NOW)
            .observe(this) { infos ->
                val running = infos.any { it.state == WorkInfo.State.RUNNING || it.state == WorkInfo.State.ENQUEUED }
                render(running)
            }

        if (Store.load(this) == null) UpdateWorker.runNow(this, forceRank = true)
    }

    override fun onResume() {
        super.onResume()
        render(false)
    }

    private fun render(loading: Boolean) {
        val snapshot = Store.load(this)
        list.text = snapshot?.let { Format.lines(this, it.stocks, withReturn = true) }
            ?: getString(R.string.empty)
        status.text = when {
            loading -> getString(R.string.loading)
            snapshot != null -> Format.asOf(snapshot.quotedAt) + " · 1시간마다 자동 갱신"
            else -> ""
        }
    }
}
