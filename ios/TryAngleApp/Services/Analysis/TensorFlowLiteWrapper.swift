import Foundation
import TensorFlowLiteC

/// TensorFlow Lite Swift Wrapper
public final class Interpreter {

    private var interpreter: OpaquePointer?

    public struct Options {
        public var threadCount: Int32 = 2
        public init() {}
    }

    public struct Tensor {
        public let data: Data
        public init(data: Data) {
            self.data = data
        }
    }

    /// Initialize interpreter with model path
    public init(modelPath: String, options: Options = Options()) throws {
        // Create TFLite model from file
        guard let model = TfLiteModelCreateFromFile(modelPath) else {
            throw InterpreterError.failedToLoadModel
        }

        // Create interpreter options
        let interpreterOptions = TfLiteInterpreterOptionsCreate()
        TfLiteInterpreterOptionsSetNumThreads(interpreterOptions, options.threadCount)

        // Create interpreter
        guard let interpreter = TfLiteInterpreterCreate(model, interpreterOptions) else {
            TfLiteModelDelete(model)
            TfLiteInterpreterOptionsDelete(interpreterOptions)
            throw InterpreterError.failedToCreateInterpreter
        }

        self.interpreter = interpreter

        // Clean up
        TfLiteModelDelete(model)
        TfLiteInterpreterOptionsDelete(interpreterOptions)
    }

    deinit {
        if let interpreter = interpreter {
            TfLiteInterpreterDelete(interpreter)
        }
    }

    /// Allocate tensors
    public func allocateTensors() throws {
        guard let interpreter = interpreter else {
            throw InterpreterError.interpreterNotReady
        }

        let status = TfLiteInterpreterAllocateTensors(interpreter)
        guard status == kTfLiteOk else {
            throw InterpreterError.failedToAllocateTensors
        }
    }

    /// Copy input data to tensor at index
    public func copy(_ data: Data, toInputAt index: Int32) throws {
        guard let interpreter = interpreter else {
            throw InterpreterError.interpreterNotReady
        }

        let inputTensor = TfLiteInterpreterGetInputTensor(interpreter, index)
        _ = data.withUnsafeBytes { bytes in
            TfLiteTensorCopyFromBuffer(inputTensor, bytes.baseAddress, data.count)
        }
    }

    /// Run inference
    public func invoke() throws {
        guard let interpreter = interpreter else {
            throw InterpreterError.interpreterNotReady
        }

        let status = TfLiteInterpreterInvoke(interpreter)
        guard status == kTfLiteOk else {
            throw InterpreterError.failedToInvoke
        }
    }

    /// Get output tensor at index
    public func output(at index: Int32) throws -> Tensor {
        guard let interpreter = interpreter else {
            throw InterpreterError.interpreterNotReady
        }

        guard let outputTensor = TfLiteInterpreterGetOutputTensor(interpreter, index) else {
            throw InterpreterError.failedToGetOutputTensor
        }

        let dataSize = TfLiteTensorByteSize(outputTensor)
        guard let dataPtr = TfLiteTensorData(outputTensor) else {
            throw InterpreterError.failedToGetTensorData
        }

        let data = Data(bytes: dataPtr, count: dataSize)
        return Tensor(data: data)
    }
}

/// TensorFlow Lite Interpreter Errors
public enum InterpreterError: Error, LocalizedError {
    case failedToLoadModel
    case failedToCreateInterpreter
    case failedToAllocateTensors
    case failedToInvoke
    case failedToGetOutputTensor
    case failedToGetTensorData
    case interpreterNotReady

    public var errorDescription: String? {
        switch self {
        case .failedToLoadModel:
            return "Failed to load TensorFlow Lite model"
        case .failedToCreateInterpreter:
            return "Failed to create TensorFlow Lite interpreter"
        case .failedToAllocateTensors:
            return "Failed to allocate tensors"
        case .failedToInvoke:
            return "Failed to invoke interpreter"
        case .failedToGetOutputTensor:
            return "Failed to get output tensor"
        case .failedToGetTensorData:
            return "Failed to get tensor data"
        case .interpreterNotReady:
            return "Interpreter not ready"
        }
    }
}

/// Module compatibility
public typealias TensorFlowLite = Interpreter