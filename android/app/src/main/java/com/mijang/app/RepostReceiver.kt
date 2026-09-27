package com.mijang.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * 알림을 늘 떠 있게 한다.
 * - 사용자가 알림을 밀어서 지우면(삭제 인텐트) 저장된 마지막 결과로 바로 다시 띄운다.
 * - 재부팅·앱 업데이트 뒤에도 다시 띄우고, 1시간 자동 갱신을 다시 건다.
 */
class RepostReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        Store.load(context)?.let { Notifier.show(context, it) }
        if (intent.action != ACTION_DISMISSED) UpdateWorker.schedule(context)
    }

    companion object {
        const val ACTION_DISMISSED = "com.mijang.app.NOTIFICATION_DISMISSED"
    }
}
