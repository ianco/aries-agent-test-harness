# Aries Framework .NET Interoperability

## Runsets with AF-.NET

| Runset | ACME<br>(Issuer) | Bob<br>(Holder) | Faber<br>(Verfier) | Mallory<br>(Holder) | Scope | Results | 
| ------ | :--------------: | :-------------: | :----------------: | :-----------------: | ----- | :-----: | 
| [acapy-dotnet-javascript](#runset-acapy-dotnet-javascript) | acapy-main<br>0.6.0 | javascript<br>1.0.0 | dotnet-master<br> | acapy-main<br>0.6.0 | AIP 1.0 | [**11 / 13<br>84%**](https://allure.vonx.io/api/allure-docker-service/projects/acapy-b-javascript-f-dotnet/reports/latest/index.html?redirect=false#behaviors) |
| [acapy-dotnet](#runset-acapy-dotnet) | acapy-main<br>0.6.0 | dotnet-master<br> | acapy-main<br>0.6.0 | acapy-main<br>0.6.0 | AIP 1.0 | [**27 / 28<br>96%**](https://allure.vonx.io/api/allure-docker-service/projects/acapy-b-dotnet/reports/latest/index.html?redirect=false#behaviors) |
| [afj-dotnet](#runset-afj-dotnet) | javascript<br>1.0.0 | dotnet-master<br> | javascript<br>1.0.0 | javascript<br>1.0.0 | AIP 1.0 | [**13 / 13<br>100%**](https://allure.vonx.io/api/allure-docker-service/projects/javascript-b-dotnet/reports/latest/index.html?redirect=false#behaviors) |
| [dotnet-acapy](#runset-dotnet-acapy) | dotnet-master<br> | acapy-main<br>0.6.0 | dotnet-master<br> | dotnet-master<br> | AIP 1.0 | [**6 / 13<br>46%**](https://allure.vonx.io/api/allure-docker-service/projects/dotnet-b-acapy/reports/latest/index.html?redirect=false#behaviors) |
| [dotnet-javascript](#runset-dotnet-javascript) | dotnet-master<br> | javascript<br>1.0.0 | dotnet-master<br> | dotnet-master<br> | AIP 1.0 | [**6 / 13<br>46%**](https://allure.vonx.io/api/allure-docker-service/projects/dotnet-b-javascript/reports/latest/index.html?redirect=false#behaviors) |
| [dotnet](#runset-dotnet) | dotnet-master<br> | dotnet-master<br> | dotnet-master<br> | dotnet-master<br> | AIP 1.0 | [**13 / 13<br>100%**](https://allure.vonx.io/api/allure-docker-service/projects/dotnet/reports/latest/index.html?redirect=false#behaviors) |

## Runset Notes

### Runset **acapy-dotnet-javascript**

Runset Name: ACA-PY to AF-.NET to AFJ

```tip
**Latest results: 11 out of 13 (84%)**


*Last run: Tue May  4 01:43:18 UTC 2021*
```

#### Current Runset Status

All tests are working, except for three tests that include Faber in the test run as an issuer.
These tests are; T001-RFC0037@1.2, T001.2-RFC0037@1.2, T001.4-RFC0037@1.1 . Further investigation 
is required to determine the issue in these three tests.

*Status Note Updated: 2021.03.18*

#### Runset Details

- Results grouped by [executed Aries RFCs executed](https://allure.vonx.io/api/allure-docker-service/projects/acapy-b-javascript-f-dotnet/reports/latest/index.html?redirect=false#behaviors)
- Results by [history](https://allure.vonx.io/allure-docker-service-ui/projects/acapy-b-javascript-f-dotnet/reports/latest)


### Runset **acapy-dotnet**

Runset Name: ACA-PY to AF-.NET

```tip
**Latest results: 27 out of 28 (96%)**


*Last run: Tue May  4 01:56:06 UTC 2021*
```

#### Current Runset Status

The majority of tests are running and passing. T013-HIPE0011 is failing due to the Aries Framework Dotnet not supporting
presentations containing a non-revocation interval, with a non-revocable credential. This issue is being tracked in 
https://github.com/hyperledger/aries-framework-dotnet/issues/184

*Status Note Updated: 2021.04.08*

#### Runset Details

- Results grouped by [executed Aries RFCs executed](https://allure.vonx.io/api/allure-docker-service/projects/acapy-b-dotnet/reports/latest/index.html?redirect=false#behaviors)
- Results by [history](https://allure.vonx.io/allure-docker-service-ui/projects/acapy-b-dotnet/reports/latest)


### Runset **afj-dotnet**

Runset Name: AFJ to AF-.NET

```tip
**Latest results: 13 out of 13 (100%)**


*Last run: Tue May  4 02:03:11 UTC 2021*
```

#### Current Runset Status

All of the tests being executed in this runset are passing.

*Status Note Updated: 2021.03.05*

#### Runset Details

- Results grouped by [executed Aries RFCs executed](https://allure.vonx.io/api/allure-docker-service/projects/javascript-b-dotnet/reports/latest/index.html?redirect=false#behaviors)
- Results by [history](https://allure.vonx.io/allure-docker-service-ui/projects/javascript-b-dotnet/reports/latest)


### Runset **dotnet-acapy**

Runset Name: AF-.NET to ACA-PY

```tip
**Latest results: 6 out of 13 (46%)**


*Last run: Tue May  4 02:22:16 UTC 2021*
```

#### Current Runset Status

More tests are failing than are passing when Aries Framework .NET is playing the issuer role. More investigation is needed.

*Status Note Updated: 2021.03.17*

#### Runset Details

- Results grouped by [executed Aries RFCs executed](https://allure.vonx.io/api/allure-docker-service/projects/dotnet-b-acapy/reports/latest/index.html?redirect=false#behaviors)
- Results by [history](https://allure.vonx.io/allure-docker-service-ui/projects/dotnet-b-acapy/reports/latest)


### Runset **dotnet-javascript**

Runset Name: AF-.NET to AFJ

```tip
**Latest results: 6 out of 13 (46%)**


*Last run: Tue May  4 02:27:11 UTC 2021*
```

#### Current Runset Status

More tests are failing than are passing when Aries Framework .NET is playing the issuer role. More investigation is needed.

*Status Note Updated: 2021.03.18*

#### Runset Details

- Results grouped by [executed Aries RFCs executed](https://allure.vonx.io/api/allure-docker-service/projects/dotnet-b-javascript/reports/latest/index.html?redirect=false#behaviors)
- Results by [history](https://allure.vonx.io/allure-docker-service-ui/projects/dotnet-b-javascript/reports/latest)


### Runset **dotnet**

Runset Name: AF-.NET to AF-.NET

```tip
**Latest results: 13 out of 13 (100%)**


*Last run: Tue May  4 02:28:05 UTC 2021*
```

#### Current Runset Status

All of the tests being executed in this runset are passing.

*Status Note Updated: 2021.03.05*

#### Runset Details

- Results grouped by [executed Aries RFCs executed](https://allure.vonx.io/api/allure-docker-service/projects/dotnet/reports/latest/index.html?redirect=false#behaviors)
- Results by [history](https://allure.vonx.io/allure-docker-service-ui/projects/dotnet/reports/latest)

Jump back to the [interoperability summary](./README.md).

