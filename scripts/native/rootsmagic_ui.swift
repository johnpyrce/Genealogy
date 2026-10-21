// Local RootsMagic 12 UI driver. Build through `./genealogy.sh doctor`.
// Commands and results are JSON; credentials are never handled here.
import AppKit
import ApplicationServices
import ScreenCaptureKit
import Vision

struct DriverError: Error, CustomStringConvertible {
    let description: String
    init(_ message: String) { description = message }
}

func attribute(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success ? value : nil
}

func stringAttribute(_ element: AXUIElement, _ name: String) -> String {
    attribute(element, name) as? String ?? ""
}

func descendants(_ element: AXUIElement, depth: Int = 0) -> [AXUIElement] {
    if depth > 16 { return [] }
    // File lists can be very large; their rows are not save-dialog controls.
    if [kAXBrowserRole, kAXOutlineRole, kAXTableRole].contains(stringAttribute(element, kAXRoleAttribute)) {
        return [element]
    }
    let children = attribute(element, kAXChildrenAttribute) as? [AXUIElement] ?? []
    return [element] + children.prefix(500).flatMap { descendants($0, depth: depth + 1) }
}

func appElement(_ pid: pid_t) -> AXUIElement {
    let element = AXUIElementCreateApplication(pid)
    AXUIElementSetMessagingTimeout(element, 2)
    return element
}

func running(_ path: String) throws -> NSRunningApplication {
    guard let bundle = Bundle(path: path), let identifier = bundle.bundleIdentifier else {
        throw DriverError("RootsMagic application not found at \(path)")
    }
    guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: identifier)
        .first(where: { $0.bundleURL?.standardizedFileURL.path == URL(fileURLWithPath: path).standardizedFileURL.path }) else {
        throw DriverError("RootsMagic is not running. Launch the installed application first.")
    }
    return app
}

func activate(_ app: NSRunningApplication) async throws {
    app.activate(options: [])
    for _ in 0..<30 {
        if NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier { return }
        try await Task.sleep(for: .milliseconds(100))
    }
    throw DriverError("Cannot activate RootsMagic. Unlock the desktop and leave the app available.")
}

func focusedWindow(_ pid: pid_t) throws -> AXUIElement {
    let element = appElement(pid)
    if let window = attribute(element, kAXFocusedWindowAttribute) { return window as! AXUIElement }
    if let windows = attribute(element, kAXWindowsAttribute) as? [AXUIElement], windows.count == 1 { return windows[0] }
    throw DriverError("Cannot identify the RootsMagic window. Close unrelated dialogs and try again.")
}

func frame(_ element: AXUIElement) throws -> CGRect {
    guard let p = attribute(element, kAXPositionAttribute), let s = attribute(element, kAXSizeAttribute) else {
        throw DriverError("Window geometry is unavailable")
    }
    var point = CGPoint.zero
    var size = CGSize.zero
    guard AXValueGetValue(p as! AXValue, .cgPoint, &point), AXValueGetValue(s as! AXValue, .cgSize, &size) else {
        throw DriverError("Window geometry could not be read")
    }
    return CGRect(origin: point, size: size)
}

func visibleWindow(_ pid: pid_t) async throws -> SCWindow {
    let target = try frame(focusedWindow(pid))
    let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
    let windows = content.windows.filter { $0.owningApplication?.processID == pid && $0.frame.width >= 100 && $0.frame.height >= 80 }
    guard let window = windows.min(by: { distance($0.frame, target) < distance($1.frame, target) }), distance(window.frame, target) < 30 else {
        throw DriverError("Cannot capture the focused RootsMagic window. Keep it visible on the current desktop.")
    }
    return window
}

func distance(_ a: CGRect, _ b: CGRect) -> CGFloat {
    abs(a.minX-b.minX) + abs(a.minY-b.minY) + abs(a.width-b.width) + abs(a.height-b.height)
}

func nativeFields(_ pid: pid_t) -> [[String: Any]] {
    descendants(appElement(pid)).compactMap { element in
        let identifier = stringAttribute(element, kAXIdentifierAttribute)
        let role = stringAttribute(element, kAXRoleAttribute)
        if identifier.isEmpty || ![kAXTextFieldRole, kAXButtonRole, kAXSheetRole].contains(role) { return nil }
        return ["identifier": identifier, "role": role,
                "value": stringAttribute(element, kAXValueAttribute), "title": stringAttribute(element, kAXTitleAttribute)]
    }
}

func snapshot(_ app: NSRunningApplication, path: String) async throws -> [String: Any] {
    let window = try await visibleWindow(app.processIdentifier)
    let configuration = SCStreamConfiguration()
    configuration.width = Int(window.frame.width * 2)
    configuration.height = Int(window.frame.height * 2)
    configuration.scalesToFit = true
    configuration.showsCursor = false
    let image = try await SCScreenshotManager.captureImage(contentFilter: SCContentFilter(desktopIndependentWindow: window), configuration: configuration)
    let bitmap = NSBitmapImageRep(cgImage: image)
    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw DriverError("Cannot encode window screenshot") }
    try png.write(to: URL(fileURLWithPath: path), options: .atomic)
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["en-US"]
    request.usesLanguageCorrection = false
    request.minimumTextHeight = 0.005
    try VNImageRequestHandler(cgImage: image).perform([request])
    let labels: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let box = observation.boundingBox
        return ["text": candidate.string, "confidence": candidate.confidence,
                "x": box.minX * window.frame.width, "y": (1-box.maxY) * window.frame.height,
                "width": box.width * window.frame.width, "height": box.height * window.frame.height]
    }
    return ["window_id": window.windowID, "window_title": stringAttribute(try focusedWindow(app.processIdentifier), kAXTitleAttribute),
            "bounds": ["x": window.frame.minX, "y": window.frame.minY, "width": window.frame.width, "height": window.frame.height],
            "labels": labels, "fields": nativeFields(app.processIdentifier), "screenshot": path]
}

func key(_ code: CGKeyCode, flags: CGEventFlags = []) throws {
    let source = CGEventSource(stateID: .combinedSessionState)
    let modifiers: [(CGKeyCode, CGEventFlags)] = [(55, .maskCommand), (56, .maskShift)]
        .filter { flags.contains($0.1) }
    var held: CGEventFlags = []
    for (modifier, flag) in modifiers {
        held.insert(flag)
        let event = CGEvent(keyboardEventSource: source, virtualKey: modifier, keyDown: true)
        event?.flags = held
        event?.post(tap: .cghidEventTap)
        Thread.sleep(forTimeInterval: 0.01)
    }
    guard let down = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: true),
          let up = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: false) else { throw DriverError("Cannot create keyboard event") }
    down.flags = flags
    up.flags = flags
    down.post(tap: .cghidEventTap)
    Thread.sleep(forTimeInterval: 0.03)
    up.post(tap: .cghidEventTap)
    for (modifier, flag) in modifiers.reversed() {
        held.remove(flag)
        let event = CGEvent(keyboardEventSource: source, virtualKey: modifier, keyDown: false)
        event?.flags = held
        event?.post(tap: .cghidEventTap)
        Thread.sleep(forTimeInterval: 0.01)
    }
}

func typeIdentifier(_ text: String) throws {
    // RootsMagic's custom edit fields ignore multi-character Unicode events.
    // Only identifiers and generation counts use keystrokes; paths use AXValue.
    let codes: [Character: CGKeyCode] = [
        "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
        "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15,
        "y": 16, "t": 17, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37,
        "j": 38, "k": 40, "n": 45, "m": 46,
        "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "9": 25,
        "7": 26, "-": 27, "8": 28, "0": 29,
    ]
    for character in text {
        guard let lower = character.lowercased().first, let code = codes[lower] else {
            throw DriverError("Only ASCII identifiers and generation counts can be typed; paths use native fields")
        }
        try key(code, flags: character.isUppercase ? .maskShift : [])
    }
}

func pressNative(_ pid: pid_t, identifier: String, value: String?) throws {
    let matches = descendants(appElement(pid)).filter { stringAttribute($0, kAXIdentifierAttribute) == identifier }
    guard matches.count == 1 else { throw DriverError("Expected one native control \(identifier); found \(matches.count)") }
    let result = value.map { AXUIElementSetAttributeValue(matches[0], kAXValueAttribute as CFString, $0 as CFString) }
        ?? AXUIElementPerformAction(matches[0], kAXPressAction as CFString)
    if result != .success { throw DriverError("Native control \(identifier) rejected the action: \(result.rawValue)") }
}

@main
struct Main {
    @MainActor
    static func main() async {
        do {
            // A command-line executable must initialize AppKit before opening
            // an application or posting events through the WindowServer.
            let application = NSApplication.shared
            application.setActivationPolicy(.prohibited)
            let input = FileHandle.standardInput.readDataToEndOfFile()
            guard let command = try JSONSerialization.jsonObject(with: input) as? [String: Any], let action = command["action"] as? String else {
                throw DriverError("Expected a JSON action on standard input")
            }
            let path = command["app"] as? String ?? "/Applications/RootsMagic 12.app"
            let bundle = Bundle(path: path)
            let trusted = AXIsProcessTrusted()
            let screen = CGPreflightScreenCaptureAccess()
            if action == "check" {
                emit(["accessibility": trusted, "screen_recording": screen, "app_exists": bundle != nil,
                      "version": bundle?.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown"])
                return
            }
            guard trusted && screen else {
                throw DriverError("Enable Accessibility and Screen Recording for the terminal that runs ./genealogy.sh in System Settings → Privacy & Security, then restart that terminal. This helper does not grant permissions automatically.")
            }
            if action == "launch" {
                let configuration = NSWorkspace.OpenConfiguration()
                configuration.activates = true
                let app = try await NSWorkspace.shared.openApplication(at: URL(fileURLWithPath: path), configuration: configuration)
                try await activate(app)
                emit(["ok": true])
                return
            }
            let app = try running(path)
            if action == "snapshot" {
                guard let destination = command["screenshot"] as? String else { throw DriverError("Missing screenshot path") }
                emit(try await snapshot(app, path: destination))
                return
            }
            try await activate(app)
            if action == "click" {
                let window = try await visibleWindow(app.processIdentifier)
                guard let expected = command["window_id"] as? UInt32, expected == window.windowID,
                      let x = command["x"] as? Double, let y = command["y"] as? Double,
                      x >= 0, y >= 0, x < window.frame.width, y < window.frame.height else {
                    throw DriverError("Window changed since observation; refusing stale click")
                }
                let point = CGPoint(x: window.frame.minX+x, y: window.frame.minY+y)
                let source = CGEventSource(stateID: .combinedSessionState)
                CGEvent(mouseEventSource: source, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left)?.post(tap: .cghidEventTap)
                for kind: CGEventType in [.leftMouseDown, .leftMouseUp] {
                    guard let event = CGEvent(mouseEventSource: source, mouseType: kind, mouseCursorPosition: point, mouseButton: .left) else {
                        throw DriverError("Cannot create mouse event")
                    }
                    event.setIntegerValueField(.mouseEventClickState, value: 1)
                    event.post(tap: .cghidEventTap)
                    try await Task.sleep(for: .milliseconds(50))
                }
            } else if action == "type" {
                guard let text = command["text"] as? String else { throw DriverError("Missing text") }
                try typeIdentifier(text)
            } else if action == "key" {
                switch command["key"] as? String {
                case "select_all": try key(0, flags: .maskCommand)
                case "go_to_folder": try key(5, flags: [.maskCommand, .maskShift])
                case "return": try key(36)
                case "tab": try key(48)
                default: throw DriverError("Unsupported key")
                }
            } else if action == "set" || action == "press" {
                guard let identifier = command["identifier"] as? String else { throw DriverError("Missing native identifier") }
                try pressNative(app.processIdentifier, identifier: identifier, value: action == "set" ? command["value"] as? String : nil)
            } else {
                throw DriverError("Unknown action \(action)")
            }
            try await Task.sleep(for: .milliseconds(250))
            emit(["ok": true])
        } catch {
            emit(["error": String(describing: error)])
            exit(1)
        }
    }

    static func emit(_ object: [String: Any]) {
        if let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]), let text = String(data: data, encoding: .utf8) {
            print(text)
        }
    }
}
