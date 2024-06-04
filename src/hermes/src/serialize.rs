/*
 * Copyright (C) 2024. Lovania
 */

//! RESP serialize

use std::io::{BufRead, BufReader, Error, ErrorKind, Read, Result};
use std::string::String;
use std::vec::Vec;

use pyo3::prelude::*;
use pyo3::types::PyTuple;
use pyo3::{pyfunction, Bound};

use super::Value;

/// up to 512 MB in length
const RESP_MAX_SIZE: i64 = 512 * 1024 * 1024;
const CRLF_BYTES: &'static [u8] = b"\r\n";
const NULL_BYTES: &'static [u8] = b"$-1\r\n";
const NULL_ARRAY_BYTES: &'static [u8] = b"*-1\r\n";

/// Encodes RESP value to RESP binary buffer.
/// # Examples
/// ```
/// # use self::resp::{Value, encode};
/// let val = Value::String("OK".to_string());
/// assert_eq!(encode(&val), vec![43, 79, 75, 13, 10]);
/// ```
pub fn encode(value: &Value) -> Vec<u8> {
    let mut res: Vec<u8> = Vec::new();
    buf_encode(value, &mut res);
    res
}

/// # Examples
/// ```
/// # use self::resp::encode_slice;
/// let array = ["SET", "a", "1"];
/// assert_eq!(encode_slice(&array),
///            "*3\r\n$3\r\nSET\r\n$1\r\na\r\n$1\r\n1\r\n".to_string().into_bytes());
/// ```
#[pyfunction]
#[pyo3(signature = (slice))]
pub fn encode_slice(slice: &Bound<'_, PyTuple>) -> Vec<u8> {
    let array: Vec<Value> = slice
        .iter()
        .map(|string| Value::Bulk(string.to_string()))
        .collect();
    let mut res: Vec<u8> = Vec::new();
    buf_encode(&Value::Array(array), &mut res);
    return res
}
#[inline]
fn buf_encode(value: &Value, buf: &mut Vec<u8>) {
    match value {
        Value::Null => {
            buf.extend_from_slice(NULL_BYTES);
        }
        Value::NullArray => {
            buf.extend_from_slice(NULL_ARRAY_BYTES);
        }
        Value::String(ref val) => {
            buf.push(b'+');
            buf.extend_from_slice(val.as_bytes());
            buf.extend_from_slice(CRLF_BYTES);
        }
        Value::Error(ref val) => {
            buf.push(b'-');
            buf.extend_from_slice(val.as_bytes());
            buf.extend_from_slice(CRLF_BYTES);
        }
        Value::Integer(ref val) => {
            buf.push(b':');
            buf.extend_from_slice(val.to_string().as_bytes());
            buf.extend_from_slice(CRLF_BYTES);
        }
        Value::Bulk(ref val) => {
            buf.push(b'$');
            buf.extend_from_slice(val.len().to_string().as_bytes());
            buf.extend_from_slice(CRLF_BYTES);
            buf.extend_from_slice(val.as_bytes());
            buf.extend_from_slice(CRLF_BYTES);
        }
        Value::BufBulk(ref val) => {
            buf.push(b'$');
            buf.extend_from_slice(val.len().to_string().as_bytes());
            buf.extend_from_slice(CRLF_BYTES);
            buf.extend_from_slice(val);
            buf.extend_from_slice(CRLF_BYTES);
        }
        Value::Array(ref val) => {
            buf.push(b'*');
            buf.extend_from_slice(val.len().to_string().as_bytes());
            buf.extend_from_slice(CRLF_BYTES);
            for item in val {
                buf_encode(item, buf);
            }
        }
    }
}

/// A streaming RESP Decoder.
#[derive(Debug)]
pub struct Decoder<R> {
    buf_bulk: bool,
    reader: BufReader<R>,
}

impl<R: Read> Decoder<R> {
    /// Creates a Decoder instance with given BufReader for decoding the RESP buffers.
    /// # Examples
    /// ```
    /// # use std::io::BufReader;
    /// # use self::resp::{Decoder, Value};
    ///
    /// let value = Value::Bulk("Hello".to_string());
    /// let buf = value.encode();
    /// let mut decoder = Decoder::new(BufReader::new(buf.as_slice()));
    /// assert_eq!(decoder.decode().unwrap(), Value::Bulk("Hello".to_string()));
    /// ```
    pub fn new(reader: BufReader<R>) -> Self {
        Decoder {
            buf_bulk: false,
            reader,
        }
    }

    /// Creates a Decoder instance with given BufReader for decoding the RESP buffers.
    /// The instance will decode bulk value to buffer bulk.
    /// # Examples
    /// ```
    /// # use std::io::BufReader;
    /// # use self::resp::{Decoder, Value};
    ///
    /// let value = Value::Bulk("Hello".to_string());
    /// let buf = value.encode();
    /// let mut decoder = Decoder::with_buf_bulk(BufReader::new(buf.as_slice()));
    /// // Always decode "$" buffers to Value::BufBulk even if feed Value::Bulk buffers
    /// assert_eq!(decoder.decode().unwrap(), Value::BufBulk("Hello".to_string().into_bytes()));
    /// ```
    pub fn with_buf_bulk(reader: BufReader<R>) -> Self {
        Decoder {
            buf_bulk: true,
            reader,
        }
    }

    /// It will read buffers from the inner BufReader, decode it to a Value.
    pub fn decode(&mut self) -> Result<Value> {
        let mut res: Vec<u8> = Vec::new();
        self.reader.read_until(b'\n', &mut res)?;

        let len = res.len();
        if len == 0 {
            return Err(Error::new(ErrorKind::UnexpectedEof, "unexpected EOF"));
        }
        if len < 3 {
            return Err(Error::new(
                ErrorKind::InvalidInput,
                format!("too short: {}", len),
            ));
        }
        if !is_crlf(res[len - 2], res[len - 1]) {
            return Err(Error::new(
                ErrorKind::InvalidInput,
                format!("invalid CRLF: {:?}", res),
            ));
        }

        let bytes = res[1..len - 2].as_ref();
        match res[0] {
            // Value::String
            b'+' => parse_string(bytes).map(Value::String),
            // Value::Error
            b'-' => parse_string(bytes).map(Value::Error),
            // Value::Integer
            b':' => parse_integer(bytes).map(Value::Integer),
            // Value::Bulk
            b'$' => {
                let int = parse_integer(bytes)?;
                if int == -1 {
                    // Null bulk
                    return Ok(Value::Null);
                }
                if int < -1 || int >= RESP_MAX_SIZE {
                    return Err(Error::new(
                        ErrorKind::InvalidInput,
                        format!("invalid bulk length: {}", int),
                    ));
                }

                let mut buf: Vec<u8> = Vec::new();
                let int = int as usize;
                buf.resize(int + 2, 0);
                self.reader.read_exact(buf.as_mut_slice())?;
                if !is_crlf(buf[int], buf[int + 1]) {
                    return Err(Error::new(
                        ErrorKind::InvalidInput,
                        format!("invalid CRLF: {:?}", buf),
                    ));
                }
                buf.truncate(int);
                if self.buf_bulk {
                    return Ok(Value::BufBulk(buf));
                }
                parse_string(buf.as_slice()).map(Value::Bulk)
            }
            // Value::Array
            b'*' => {
                let int = parse_integer(bytes)?;
                if int == -1 {
                    // Null array
                    return Ok(Value::NullArray);
                }
                if int < -1 || int >= RESP_MAX_SIZE {
                    return Err(Error::new(
                        ErrorKind::InvalidInput,
                        format!("invalid array length: {}", int),
                    ));
                }

                let mut array: Vec<Value> = Vec::with_capacity(int as usize);
                for _ in 0..int {
                    let val = self.decode()?;
                    array.push(val);
                }
                Ok(Value::Array(array))
            }
            prefix => Err(Error::new(
                ErrorKind::InvalidInput,
                format!("invalid RESP type: {:?}", prefix),
            )),
        }
    }
}

#[inline]
fn is_crlf(a: u8, b: u8) -> bool {
    a == b'\r' && b == b'\n'
}

#[inline]
fn parse_string(bytes: &[u8]) -> Result<String> {
    String::from_utf8(bytes.to_vec()).map_err(|err| Error::new(ErrorKind::InvalidData, err))
}

#[inline]
fn parse_integer(bytes: &[u8]) -> Result<i64> {
    let str_integer = parse_string(bytes)?;
    str_integer
        .parse::<i64>()
        .map_err(|err| Error::new(ErrorKind::InvalidData, err))
}
