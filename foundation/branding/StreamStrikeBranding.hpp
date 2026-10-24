#pragma once

// StreamStrike presentation-only identity for the pinned OBS frontend.
// Original product PNG is retained unchanged; badges convey output state only.
#include <QColor>
#include <QIcon>
#include <QPen>
#include <QPainter>
#include <QPixmap>

namespace StreamStrikeBranding {
enum class State { Idle, Active, Paused };

inline QIcon icon(State state = State::Idle)
{
	const QPixmap master(QStringLiteral(":/res/images/streamstrike.png"));
	if (master.isNull())
		return {};
	if (state == State::Idle)
		return QIcon(master);

	QPixmap marked = master;
	QPainter painter(&marked);
	painter.setRenderHint(QPainter::Antialiasing);
	painter.setPen(QPen(Qt::white, 24));
	painter.setBrush(state == State::Active ? QColor(225, 42, 55) : QColor(244, 174, 30));
	painter.drawEllipse(QPointF(864, 864), 116, 116);
	if (state == State::Paused) {
		// Knock out the pause bars so a native monochrome tray template also
		// distinguishes paused from active; color alone is not sufficient.
		painter.setCompositionMode(QPainter::CompositionMode_Clear);
		painter.setPen(Qt::NoPen);
		painter.setBrush(Qt::transparent);
		painter.drawRoundedRect(QRectF(815, 804, 32, 120), 6, 6);
		painter.drawRoundedRect(QRectF(881, 804, 32, 120), 6, 6);
	}
	painter.end();
	return QIcon(marked);
}

inline QIcon trayIcon(State state = State::Idle)
{
	QIcon result = icon(state);
#ifdef __APPLE__
	// Preserve upstream native macOS tray-template semantics.
	result.setIsMask(true);
#endif
	return result;
}
} // namespace StreamStrikeBranding
