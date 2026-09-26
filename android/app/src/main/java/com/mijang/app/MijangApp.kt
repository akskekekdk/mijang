package com.mijang.app

import android.app.Application

class MijangApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Notifier.createChannel(this)
        UpdateWorker.schedule(this)
    }
}
