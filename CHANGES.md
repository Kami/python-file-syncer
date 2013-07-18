0.4.1 - 2013-07-19

* Allow user to specify `--no-content-type` option. If this option is specified,
  program won't automatically send `application/octet-stream` Content-Type
  header with each file, but it will use automatic content type detection
  from the underlying Libcloud library. (#9)
  [Alex Meng]

0.4.0 - 2013-07-17

* Allow user to specify a `--region` option for the provider drivers which
  support multiple regions. (#8)
  [Samuel Toriel]

* Bump minimum version for Libcloud dependency to 0.13.0.

0.3.2 - 2013-04-24

* Create a local directory hierarchy if it doesn't exist when using a restore
  option. (#7)
  [Ryan Philips]

0.3.1 - 2013-02-20

* Fix a bug with supported providers.

0.2.1 - 2012-09-14

* Add support for retries to all the remote operations. (#4)
  [Ryan Philips]

0.2.0 - 2012-08-23

* Add restore functionality (#3)
 [Ryan Philips]

0.1.1 - 2012-07-24

* Allow user to specify exclude patterns using --exclude option
* Perform deletes and uploads in parallel

0.1.0 - 2012-07-23

* Initial release
