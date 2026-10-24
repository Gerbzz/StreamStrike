#pragma once

// Opt-in native verification only. This never starts an OBS output or source.
#include "StreamStrikeBranding.hpp"

#include <QApplication>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QScreen>
#include <QSystemTrayIcon>
#include <QTimer>
#include <QWidget>
#include <QWindow>

#include <memory>

namespace StreamStrikeCapture {
inline bool writeNew(const QString &path, const QByteArray &bytes)
{
	QFile file(path);
	if (!file.open(QIODevice::WriteOnly | QIODevice::NewOnly))
		return false;
	return file.write(bytes) == bytes.size() && file.flush();
}

inline bool saveNew(const QString &path, const QPixmap &pixels)
{
	QFile file(path);
	if (pixels.isNull() || !file.open(QIODevice::WriteOnly | QIODevice::NewOnly))
		return false;
	return pixels.save(&file, "PNG") && file.flush();
}

inline QByteArray fileSHA256(const QString &path)
{
	QFile file(path);
	if (!file.open(QIODevice::ReadOnly))
		return {};
	QCryptographicHash digest(QCryptographicHash::Sha256);
	if (!digest.addData(&file) || file.error() != QFileDevice::NoError)
		return {};
	return digest.result().toHex();
}

inline bool schedule(QWidget *window, QSystemTrayIcon *tray)
{
	const QByteArray requested = qgetenv("STREAMSTRIKE_CAPTURE_DIR");
	if (requested.isEmpty())
		return false;

	const QByteArray nonce = qgetenv("STREAMSTRIKE_CAPTURE_NONCE");
	bool validNonce = nonce.size() == 32;
	for (char value : nonce)
		validNonce = validNonce && ((value >= '0' && value <= '9') || (value >= 'a' && value <= 'f'));

	const QByteArray buildIdentity = qgetenv("STREAMSTRIKE_BUILD_IDENTITY");
	bool validBuildIdentity = buildIdentity.size() == 64;
	for (char value : buildIdentity)
		validBuildIdentity = validBuildIdentity && ((value >= '0' && value <= '9') || (value >= 'a' && value <= 'f'));

	const QString output = QString::fromLocal8Bit(requested);
	const QPointer<QWidget> guardedWindow(window);
	const QPointer<QSystemTrayIcon> guardedTray(tray);
	// The host must create an empty dedicated directory. Never overwrite old proof.
	const QFileInfo directory(output);
	const bool usableDirectory = directory.isAbsolute() && directory.isDir() && !directory.isSymLink() &&
				     QDir(output).entryList(QDir::AllEntries | QDir::NoDotAndDotDot |
							   QDir::Hidden | QDir::System).isEmpty();
	const auto fail = [guardedWindow, output, usableDirectory](const QString &reason) {
		qCritical("StreamStrike native verification failed: %s", qPrintable(reason));
		if (usableDirectory) {
			const QJsonObject failure{{"status", "failed"}, {"reason", reason}};
			writeNew(QDir(output).filePath("failure.json"), QJsonDocument(failure).toJson());
		}
		if (guardedWindow)
			guardedWindow->close(); // Follow normal OBS shutdown, never hard-exit it.
	};
	if (!validNonce) {
		QTimer::singleShot(0, qApp, [fail] { fail("capture nonce must be exactly 32 lowercase hex characters"); });
		return true;
	}
	if (!validBuildIdentity) {
		QTimer::singleShot(0, qApp, [fail] { fail("build identity must be exactly 64 lowercase hex characters"); });
		return true;
	}
	if (!usableDirectory || !guardedWindow || !guardedTray) {
		QTimer::singleShot(0, qApp, [fail] { fail("missing actual window/tray or empty output directory"); });
		return true;
	}

	// Wait on native exposure rather than capture a widget reconstruction.
	auto attempts = std::make_shared<int>(0);
	auto timer = new QTimer(window);
	timer->setInterval(100);
	QObject::connect(timer, &QTimer::timeout, window,
			 [timer, attempts, guardedWindow, guardedTray, output, nonce, buildIdentity, fail] {
		if (!guardedWindow || !guardedTray) {
			timer->stop();
			fail("actual window or tray disappeared");
			return;
		}
		if (QGuiApplication::platformName() != QStringLiteral("xcb")) {
			timer->stop();
			fail("native Linux xcb platform required; offscreen/minimal/Wayland are not this gate");
			return;
		}
		const bool ready = guardedWindow->isVisible() && guardedWindow->windowHandle() &&
				   guardedWindow->windowHandle()->isExposed() && guardedWindow->screen() &&
				   guardedWindow->frameGeometry().height() > guardedWindow->height() &&
				   QSystemTrayIcon::isSystemTrayAvailable() && guardedTray->isVisible() &&
				   !QApplication::activeModalWidget();
		if (!ready) {
			if (++*attempts >= 600) {
				timer->stop();
				fail("native exposure/tray/modal readiness timed out");
			}
			return;
		}
		timer->stop();

		const QByteArray executableHash = fileSHA256(QCoreApplication::applicationFilePath());
		if (executableHash.isEmpty()) {
			fail("actual running executable could not be hashed");
			return;
		}

		QFile resource(QStringLiteral(":/res/images/streamstrike.png"));
		if (!resource.open(QIODevice::ReadOnly)) {
			fail("compiled master resource unreadable");
			return;
		}
		const QByteArray bytes = resource.readAll();
		const QByteArray hash = QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex();
		if (hash != "86acca5004fbe90a471230159b452d3eb4a3663db30dac5d26523f43f470d926") {
			fail("compiled master resource identity mismatch");
			return;
		}
		if (!guardedWindow->windowTitle().startsWith(QStringLiteral("StreamStrike - OBS "))) {
			fail("actual window title is not the branded OBS frontend");
			return;
		}

		const QPixmap applicationIcon = qApp->windowIcon().pixmap(256, 256);
		const QPixmap windowIcon = guardedWindow->windowIcon().pixmap(256, 256);
		const QIcon originalTray = guardedTray->icon();
		const QPixmap idle = originalTray.pixmap(256, 256);
		// Presentation-only state readbacks on the ACTUAL tray object. Do not call
		// OnActivate/PauseRecording: those methods change media/output state.
		guardedTray->setIcon(StreamStrikeBranding::trayIcon(StreamStrikeBranding::State::Active));
		const QPixmap active = guardedTray->icon().pixmap(256, 256);
		guardedTray->setIcon(StreamStrikeBranding::trayIcon(StreamStrikeBranding::State::Paused));
		const QPixmap paused = guardedTray->icon().pixmap(256, 256);
		guardedTray->setIcon(originalTray);
		const QImage expected = StreamStrikeBranding::icon().pixmap(256, 256).toImage();
		if (applicationIcon.isNull() || windowIcon.isNull() || idle.isNull() || active.isNull() ||
		    paused.isNull() || applicationIcon.toImage() != expected || windowIcon.toImage() != expected ||
		    idle.toImage() != expected || active.toImage() == paused.toImage() || active.toImage() == expected ||
		    paused.toImage() == expected) {
			fail("actual application/window/tray resource or status pixels differ");
			return;
		}

		const WId id = guardedWindow->winId();
		const QRect frame = guardedWindow->frameGeometry();
		if (!guardedWindow->screen()->geometry().contains(frame)) {
			fail("native window frame is not fully inside the capture screen");
			return;
		}
		// Read the actual root framebuffer region, including the WM title/icon.
		// No QWidget::grab/render, reconstructed decorations, or image composition.
		const QPixmap native = guardedWindow->screen()->grabWindow(0, frame.x(), frame.y(), frame.width(),
									 frame.height());
		if (native.isNull() || native.width() < 800 || native.height() < 500) {
			fail("native window framebuffer is missing or unexpectedly small");
			return;
		}
		const QDir dir(output);
		bool saved = writeNew(dir.filePath("resource.png"), bytes);
		saved = saveNew(dir.filePath("application-icon.png"), applicationIcon) && saved;
		saved = saveNew(dir.filePath("window-icon.png"), windowIcon) && saved;
		saved = saveNew(dir.filePath("tray-icon.png"), idle) && saved;
		saved = saveNew(dir.filePath("state-active.png"), active) && saved;
		saved = saveNew(dir.filePath("state-paused.png"), paused) && saved;
		saved = saveNew(dir.filePath("native.png"), native) && saved;
		if (!saved) {
			fail("one or more native artifacts could not be written without overwrite");
			return;
		}
		QJsonObject artifactHashes;
		const char *artifactNames[] = {"resource.png", "application-icon.png", "window-icon.png", "tray-icon.png",
					       "state-active.png", "state-paused.png", "native.png"};
		for (const char *name : artifactNames) {
			const QByteArray artifactHash = fileSHA256(dir.filePath(QString::fromLatin1(name)));
			if (artifactHash.isEmpty()) {
				fail("saved native artifact could not be hashed");
				return;
			}
			artifactHashes.insert(QString::fromLatin1(name), QString::fromLatin1(artifactHash));
		}
		const QJsonObject receipt{{"status", "captured"},
			{"captureNonce", QString::fromLatin1(nonce)},
			{"buildIdentitySHA256", QString::fromLatin1(buildIdentity)},
			{"executableSHA256", QString::fromLatin1(executableHash)},
			{"artifactSHA256", artifactHashes},
			{"kind", "native-window-framebuffer"},
			{"platform", QGuiApplication::platformName()},
			{"title", guardedWindow->windowTitle()},
			{"width", native.width()}, {"height", native.height()},
			{"resourceSHA256", QString::fromLatin1(hash)},
			{"nativeWindowId", QString::number(static_cast<qulonglong>(id))},
			{"captureMethod", "QScreen::grabWindow(root,frameGeometry)"},
			{"captureRegion", QJsonArray{frame.x(), frame.y(), frame.width(), frame.height()}},
			{"trayAvailable", QSystemTrayIcon::isSystemTrayAvailable()},
			{"trayVisible", guardedTray->isVisible()},
			{"iconStateProof", "actual-tray-object-presentation-only"},
			{"capturedUTC", QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)}};
		if (!writeNew(dir.filePath("runtime.json"), QJsonDocument(receipt).toJson())) {
			fail("native capture receipt could not be written");
			return;
		}
		guardedWindow->close();
	});
	timer->start();
	return true;
}
} // namespace StreamStrikeCapture
